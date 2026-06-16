import RPi.GPIO as GPIO
import time

PIR_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(PIR_PIN, GPIO.IN)

print("PIR sensor initializing... wait 30 seconds for it to calibrate")
time.sleep(30)
print("Ready. Waiting for motion...")

try:
    while True:
        if GPIO.input(PIR_PIN):
            print(f"Motion detected! - {time.strftime('%H:%M:%S')}")
            time.sleep(2)
        time.sleep(0.1)

except KeyboardInterrupt:
    print("Stopping...")
    GPIO.cleanup()
