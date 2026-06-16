import RPi.GPIO as GPIO
import time

TRIG_PIN = 23
ECHO_PIN = 24

GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG_PIN, GPIO.OUT)
GPIO.setup(ECHO_PIN, GPIO.IN)

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

    pulse_start = time.time()

    timeout = time.time() + 0.04
    while GPIO.input(ECHO_PIN) == 1:
        if time.time() > timeout:
            return None

    pulse_end = time.time()
    pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 17150
    return round(distance, 2)

print("Ultrasonic sensor ready. Reading distance...")

try:
    while True:
        dist = get_distance()
        if dist is not None:
            print(f"Distance: {dist} cm - {time.strftime('%H:%M:%S')}")
        else:
            print("Out of range")
        time.sleep(1)

except KeyboardInterrupt:
    print("Stopping...")
    GPIO.cleanup()
