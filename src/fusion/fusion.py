import RPi.GPIO as GPIO
import cv2
import time
import threading
from picamera2 import Picamera2
import board
import busio
import adafruit_ssd1306
from PIL import Image, ImageDraw

# ─── Pin config ───────────────────────────────────────────
PIR_PIN   = 17
TRIG_PIN  = 23
ECHO_PIN  = 24
SERVO_PIN = 18

# ─── GPIO setup ───────────────────────────────────────────
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIR_PIN,   GPIO.IN)
GPIO.setup(TRIG_PIN,  GPIO.OUT)
GPIO.setup(ECHO_PIN,  GPIO.IN)
GPIO.setup(SERVO_PIN, GPIO.OUT)

pwm = GPIO.PWM(SERVO_PIN, 50)
pwm.start(0)

# ─── OLED setup ───────────────────────────────────────────
i2c  = busio.I2C(board.SCL, board.SDA)
oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)

def oled_show(line1="", line2="", line3=""):
    img  = Image.new("1", (oled.width, oled.height))
    draw = ImageDraw.Draw(img)
    draw.text((0,  0), line1, fill=255)
    draw.text((0, 22), line2, fill=255)
    draw.text((0, 44), line3, fill=255)
    oled.image(img)
    oled.show()

def oled_clear():
    oled.fill(0)
    oled.show()

# ─── Servo ────────────────────────────────────────────────
def servo_angle(angle):
    duty = 2 + (angle / 18)
    pwm.ChangeDutyCycle(duty)
    time.sleep(0.5)
    pwm.ChangeDutyCycle(0)

# ─── Ultrasonic ───────────────────────────────────────────
def get_distance():
    GPIO.output(TRIG_PIN, False)
    time.sleep(0.01)
    GPIO.output(TRIG_PIN, True)
    time.sleep(0.00001)
    GPIO.output(TRIG_PIN, False)

    timeout = time.time() + 0.04
    while GPIO.input(ECHO_PIN) == 0:
        if time.time() > timeout:
            return None

    start = time.time()
    timeout = time.time() + 0.04
    while GPIO.input(ECHO_PIN) == 1:
        if time.time() > timeout:
            return None

    return round((time.time() - start) * 17150, 2)

# ─── Camera ───────────────────────────────────────────────
picam2   = Picamera2()
picam2.configure(picam2.create_preview_configuration(
    main={"format": "RGB888", "size": (640, 480)}
))
picam2.start()
time.sleep(2)

back_sub = cv2.createBackgroundSubtractorMOG2(
    history=500, varThreshold=50, detectShadows=False
)

# ─── Shared state ─────────────────────────────────────────
state = {
    "pir":      False,
    "distance": None,
    "camera":   False,
    "target_x": 320,
}

# ─── Sensor threads ───────────────────────────────────────
def pir_thread():
    GPIO.setmode(GPIO.BCM)
    while True:
        state["pir"] = bool(GPIO.input(PIR_PIN))
        time.sleep(0.1)

def ultrasonic_thread():
    GPIO.setmode(GPIO.BCM)
    while True:
        state["distance"] = get_distance()
        time.sleep(0.5)

def camera_thread():
    while True:
        frame    = picam2.capture_array()
        gray     = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        blur     = cv2.GaussianBlur(gray, (21, 21), 0)
        mask     = back_sub.apply(blur)
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        largest = max(contours, key=cv2.contourArea, default=None)
        if largest is not None and cv2.contourArea(largest) > 1500:
            x, y, w, h = cv2.boundingRect(largest)
            state["camera"] = True
            state["target_x"] = x + w // 2
        else:
            state["camera"] = False
            state["target_x"] = 320
        time.sleep(0.2)

# ─── Fusion logic ─────────────────────────────────────────
def get_score():
    score = 0
    if state["pir"]:
        score += 1
    if state["distance"] and state["distance"] < 150:
        score += 1
    if state["camera"]:
        score += 1
    return score

def alert(score):
    print(f"\n🚨 THREAT CONFIRMED (score {score}/3)")
    print(f"   PIR: {state['pir']} | "
          f"Distance: {state['distance']}cm | "
          f"Camera: {state['camera']}")
    oled_show("!! ALERT !!", f"Score: {score}/3",
              f"Dist: {state['distance']}cm")
    angle = int(180 - (state["target_x"] / 640) * 180)
    print(f"   Tracking to angle: {angle}°")
    servo_angle(angle)

# ─── Main ─────────────────────────────────────────────────
print("Surveillance system starting...")
oled_show("SURVEILLANCE", "SYSTEM", "ONLINE")
time.sleep(2)

threading.Thread(target=pir_thread,        daemon=True).start()
threading.Thread(target=ultrasonic_thread, daemon=True).start()
threading.Thread(target=camera_thread,     daemon=True).start()

print("All sensors active. Monitoring...\n")

try:
    while True:
        score = get_score()
        dist  = state["distance"]
        dist_str = f"{dist}cm" if dist else "---"

        print(f"[{time.strftime('%H:%M:%S')}] "
              f"Score: {score}/3 | "
              f"PIR: {int(state['pir'])} | "
              f"Dist: {dist_str} | "
              f"Cam: {int(state['camera'])}")

        if score >= 3:
            alert(score)
        else:
            oled_show("MONITORING",
                      f"Score: {score}/3",
                      f"Dist: {dist_str}")

        time.sleep(1)

except KeyboardInterrupt:
    print("\nShutting down...")
    oled_clear()
    pwm.stop()
    GPIO.cleanup()
    picam2.stop()
    print("Done")
