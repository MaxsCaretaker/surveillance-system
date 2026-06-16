import cv2
import numpy as np
from picamera2 import Picamera2
import time

# Initialize camera
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(
    main={"format": "RGB888", "size": (640, 480)}
))
picam2.start()
time.sleep(2)

# Background subtractor
back_sub = cv2.createBackgroundSubtractorMOG2(
    history=500,
    varThreshold=50,
    detectShadows=False
)

print("Camera motion detection running... press Ctrl+C to stop")

motion_count = 0

try:
    while True:
        frame = picam2.capture_array()
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        blur = cv2.GaussianBlur(gray, (21, 21), 0)

        fg_mask = back_sub.apply(blur)
        contours, _ = cv2.findContours(
            fg_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        motion_detected = False
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 1500:  # filter small noise
                motion_detected = True
                x, y, w, h = cv2.boundingRect(contour)
                print(f"Motion detected - Area: {area:.0f}px "
                      f"Position: ({x},{y}) "
                      f"Size: {w}x{h} - "
                      f"{time.strftime('%H:%M:%S')}")

        if not motion_detected:
            print(f"No motion - {time.strftime('%H:%M:%S')}")

        time.sleep(0.5)

except KeyboardInterrupt:
    print("Stopping...")
    picam2.stop()
