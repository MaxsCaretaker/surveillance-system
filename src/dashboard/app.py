from flask import Flask, Response, jsonify, render_template_string
import cv2
import time
import threading
import RPi.GPIO as GPIO
from picamera2 import Picamera2
import board
import busio
import adafruit_ssd1306
from PIL import Image, ImageDraw

app = Flask(__name__)

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

# ─── OLED ─────────────────────────────────────────────────
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
picam2 = Picamera2()
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
    "score":    0,
    "events":   [],
}
frame_lock   = threading.Lock()
current_frame = None

# ─── Sensor threads ───────────────────────────────────────
def pir_thread():
    while True:
        state["pir"] = bool(GPIO.input(PIR_PIN))
        time.sleep(0.1)

def ultrasonic_thread():
    while True:
        state["distance"] = get_distance()
        time.sleep(0.5)

def camera_thread():
    global current_frame
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
            state["camera"]   = True
            state["target_x"] = x + w // 2
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.circle(frame, (x + w//2, y + h//2), 5, (0, 255, 0), -1)
        else:
            state["camera"]   = False
            state["target_x"] = 320

        bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        with frame_lock:
            current_frame = bgr
        time.sleep(0.1)

def fusion_thread():
    while True:
        score = 0
        if state["pir"]:                                    score += 1
        if state["distance"] and state["distance"] < 150:  score += 1
        if state["camera"]:                                 score += 1
        state["score"] = score

        if score >= 3:
            ts  = time.strftime('%H:%M:%S')
            dist = state["distance"]
            event = f"{ts} | THREAT 3/3 | Dist: {dist}cm | Angle: {int(180-(state['target_x']/640)*180)}°"
            state["events"].insert(0, event)
            state["events"] = state["events"][:20]
            oled_show("!! ALERT !!", f"Score: {score}/3", f"Dist: {dist}cm")
            servo_angle(int(180 - (state["target_x"] / 640) * 180))
        else:
            dist_str = f"{state['distance']}cm" if state["distance"] else "---"
            oled_show("MONITORING", f"Score: {score}/3", f"Dist: {dist_str}")

        time.sleep(1)

# ─── Video stream ─────────────────────────────────────────
def generate_frames():
    while True:
        with frame_lock:
            frame = current_frame
        if frame is None:
            time.sleep(0.1)
            continue
        _, buf = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' +
               buf.tobytes() + b'\r\n')
        time.sleep(0.05)

# ─── Routes ───────────────────────────────────────────────
@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/video')
def video():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    dist = state["distance"]
    return jsonify({
        "pir":      state["pir"],
        "distance": f"{dist}cm" if dist else "---",
        "camera":   state["camera"],
        "score":    state["score"],
        "events":   state["events"][:10],
    })

# ─── HTML ─────────────────────────────────────────────────
HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Surveillance System</title>
  <style>
    body { background:#0a0a0a; color:#00ff88; font-family:monospace; margin:0; padding:20px; }
    h1   { font-size:1.4em; letter-spacing:4px; border-bottom:1px solid #00ff88; padding-bottom:10px; }
    .grid { display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-top:20px; }
    .card { background:#111; border:1px solid #1a1a1a; padding:16px; border-radius:4px; }
    .label { color:#555; font-size:0.75em; letter-spacing:2px; margin-bottom:4px; }
    .value { font-size:1.6em; }
    .score-0, .score-1 { color:#00ff88; }
    .score-2 { color:#ffaa00; }
    .score-3 { color:#ff3333; }
    img { width:100%; max-height:360px; object-fit:contain; border:1px solid #1a1a1a; border-radius:4px; }
    .event { font-size:0.8em; color:#aaa; padding:4px 0; border-bottom:1px solid #1a1a1a; }
    .full  { grid-column: span 2; }
  </style>
</head>
<body>
  <h1>⚡ PERIMETER SURVEILLANCE</h1>
  <div class="grid">
    <div class="card full">
      <div class="label">LIVE FEED</div>
      <img src="/video" />
    </div>
    <div class="card">
      <div class="label">THREAT SCORE</div>
      <div class="value score-0" id="score">--</div>
    </div>
    <div class="card">
      <div class="label">DISTANCE</div>
      <div class="value" id="dist">--</div>
    </div>
    <div class="card">
      <div class="label">PIR</div>
      <div class="value" id="pir">--</div>
    </div>
    <div class="card">
      <div class="label">CAMERA</div>
      <div class="value" id="cam">--</div>
    </div>
    <div class="card full">
      <div class="label">EVENT LOG</div>
      <div id="events"></div>
    </div>
  </div>
  <script>
    async function update() {
      const r = await fetch('/status');
      const d = await r.json();
      document.getElementById('score').textContent = d.score + '/3';
      document.getElementById('score').className = 'value score-' + d.score;
      document.getElementById('dist').textContent = d.distance;
      document.getElementById('pir').textContent  = d.pir ? 'ACTIVE' : 'CLEAR';
      document.getElementById('cam').textContent  = d.camera ? 'MOTION' : 'CLEAR';
      document.getElementById('events').innerHTML =
        d.events.map(e => `<div class="event">${e}</div>`).join('');
    }
    setInterval(update, 1000);
    update();
  </script>
</body>
</html>
"""

# ─── Start ────────────────────────────────────────────────
if __name__ == '__main__':
    oled_show("SURVEILLANCE", "SYSTEM", "ONLINE")
    threading.Thread(target=pir_thread,        daemon=True).start()
    threading.Thread(target=ultrasonic_thread, daemon=True).start()
    threading.Thread(target=camera_thread,     daemon=True).start()
    threading.Thread(target=fusion_thread,     daemon=True).start()
    print(f"\nDashboard running at http://Pi-Project.local:5000\n")
    app.run(host='0.0.0.0', port=5000, threaded=True)
