# System Architecture — Autonomous Perimeter Surveillance System

## Overview

This system is a multi-sensor autonomous perimeter surveillance platform built
on a Raspberry Pi 4. It fuses data from three independent sensors to detect
and track intruders in a defined perimeter zone, displays live status on an
OLED screen, physically tracks detected targets with a servo-mounted camera,
and streams a live command and control dashboard over the local network.

The design is intentionally analogous to autonomous perimeter monitoring
systems used in defense and border security contexts — specifically, the
principle that no single sensor should be trusted in isolation.

---

## Sensor Fusion Pipeline

### The Problem
Each sensor alone is unreliable:
- PIR (passive infrared) triggers on any heat source — sunlight, appliances,
  animals
- Ultrasonic distance sensors return noisy readings and detect any object
  regardless of whether it is a threat
- Computer vision background subtraction fires on lighting changes, shadows,
  and camera noise

Relying on any single sensor produces an unacceptable false positive rate.

### The Solution
A confidence scoring system requires agreement across all three sensors before
declaring a confirmed detection:

| Sensor | Condition | Score |
|---|---|---|
| PIR | Motion detected | +1 |
| Ultrasonic | Object within 150cm | +1 |
| Camera | Motion contour > 1500px² | +1 |

A score of 3/3 triggers a confirmed threat event. This mirrors the multi-modal
sensor fusion approach used in real autonomous detection systems, where
corroborating evidence from independent modalities dramatically reduces false
positive rates.

### Design Tradeoffs
- **Threshold of 150cm for ultrasonic** — chosen to cover a standard doorway
  approach distance while ignoring background furniture. In a production system
  this would be configurable per deployment zone.
- **Contour area threshold of 1500px²** — empirically tuned to filter camera
  noise while reliably detecting a human-sized moving object at 1-3 meters.
  A production system would replace background subtraction with a trained
  object detector (e.g. YOLOv8-nano on TensorFlow Lite).
- **Requiring 3/3 vs 2/3** — a 2/3 threshold generates too many false
  positives in a home environment with a noisy PIR sensor. 3/3 is conservative
  but appropriate for a prototype where false positives undermine trust in
  the system.

---

## Servo Tracking

When a threat is confirmed, the servo pans to point toward the detected target
using the camera's bounding box centroid:

angle = 180 - (target_x / frame_width) * 180

This maps the horizontal pixel position of the largest detected contour to a
servo angle between 0° and 180°. The servo physically points the camera toward
the target zone.

### Limitations
- The SG90 servo has approximately ±5° of mechanical error
- Tracking updates only on confirmed threat events, not continuously
- A production system would run a PID controller for smooth continuous tracking
  and use a higher-torque servo with encoder feedback

---

## Concurrency Model

The system runs five concurrent threads:

| Thread | Responsibility | Update Rate |
|---|---|---|
| `pir_thread` | Poll GPIO pin 17 | 10 Hz |
| `ultrasonic_thread` | Trigger/read HC-SR04 | 2 Hz |
| `camera_thread` | Capture frame, run CV pipeline | 5 Hz |
| `fusion_thread` | Score sensors, trigger alerts | 1 Hz |
| Flask main thread | Serve HTTP dashboard | On request |

All sensor state is stored in a shared Python dictionary. In a production
system this would use proper mutex locking or a message queue (e.g. ZeroMQ)
to prevent race conditions between threads reading and writing state
simultaneously.

---

## Command and Control Dashboard

The Flask web dashboard exposes three HTTP endpoints:

- `GET /` — serves the HTML dashboard
- `GET /video` — MJPEG stream from the Pi Camera using multipart HTTP response
- `GET /status` — JSON snapshot of current sensor state and event log

The dashboard auto-updates sensor readings every 1 second via JavaScript
polling and displays a live MJPEG camera feed with OpenCV bounding boxes
overlaid on detected motion contours.

### Why Flask over a heavier framework
Flask was chosen for simplicity and low overhead on the Pi's limited CPU.
The dashboard is intended as a local network C2 interface, not a
public-facing web application. A production system would use a proper WSGI
server (Gunicorn) and consider WebSocket streaming for lower latency updates.

---

## Hardware Communication Protocols

| Component | Protocol | Pi Interface |
|---|---|---|
| PIR sensor | Digital GPIO (3.3V logic) | GPIO 17 |
| Ultrasonic sensor | GPIO trigger/echo timing | GPIO 23/24 |
| Servo motor | PWM (50Hz, 1-2ms pulse) | GPIO 18 |
| OLED display | I2C (address 0x3C) | GPIO 2/3 (SDA/SCL) |
| Camera | MIPI CSI-2 | CSI ribbon connector |

---

## What a Production Version Would Look Like

1. **Replace background subtraction with YOLOv8-nano** — trained object
   detector running on TensorFlow Lite, enabling person/vehicle/animal
   classification rather than generic motion detection
2. **Add a second sensor node** — a second Pi communicating over the network,
   creating a distributed multi-node detection system
3. **Replace Flask polling with WebSockets** — sub-100ms dashboard latency
4. **Add persistent event logging** — SQLite database with timestamped events,
   exportable for after-action review
5. **Harden the power supply** — dedicated 5V 3A supply for the servo,
   separate from the Pi's supply rail, with capacitors to suppress voltage
   spikes
6. **Enclose the hardware** — weatherproof enclosure with cable management
   for outdoor deployment

---

## Repository Structure
surveillance-system/

├── src/

│   ├── sensors/          # Hardware drivers (PIR, ultrasonic, OLED, servo)

│   ├── vision/           # OpenCV motion detection pipeline

│   ├── fusion/           # Multi-sensor fusion logic

│   └── dashboard/        # Flask web application

├── hardware/             # Wiring diagrams and parts list

├── docs/

│   └── architecture.md   # This document

├── demo/                 # Demo video and screenshots

└── README.md
