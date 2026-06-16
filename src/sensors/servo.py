import RPi.GPIO as GPIO
import time

SERVO_PIN = 18

GPIO.setmode(GPIO.BCM)
GPIO.setup(SERVO_PIN, GPIO.OUT)

pwm = GPIO.PWM(SERVO_PIN, 50)  # 50Hz frequency
pwm.start(0)

def set_angle(angle):
    duty = 2 + (angle / 18)
    pwm.ChangeDutyCycle(duty)
    time.sleep(0.5)
    pwm.ChangeDutyCycle(0)  # stop jitter

print("Testing servo motor...")

try:
    print("Center (90 degrees)")
    set_angle(90)
    time.sleep(1)

    print("Left (0 degrees)")
    set_angle(0)
    time.sleep(1)

    print("Right (180 degrees)")
    set_angle(180)
    time.sleep(1)

    print("Back to center")
    set_angle(90)
    time.sleep(1)

except KeyboardInterrupt:
    pass

finally:
    pwm.stop()
    GPIO.cleanup()
    print("Done")
