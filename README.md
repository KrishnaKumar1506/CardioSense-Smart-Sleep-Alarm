# CardioSense: IoT & ML Powered Cardiac Sleep Detection with Smart Alarm

## Overview
**CardioSense** is an IoT-based smart sleep monitoring system that analyzes cardiac activity during sleep and triggers an alarm when the user reaches a natural wake-up state. The system improves wake-up efficiency and promotes better sleep quality through real-time heart rate monitoring and sleep stage detection.

The project integrates **Arduino-based hardware sensing with Machine Learning models** to analyze heart rate and ECG signals. It provides two operating modes: a threshold-based detection system and an ML-based sleep stage classification system.

---

## Key Features
- Real-time heart rate monitoring using pulse and ECG sensors
- Smart alarm system that triggers during the awake/light sleep state
- Two operating modes for sleep detection
- Machine Learning based sleep stage classification
- Python GUI interface for user interaction
- Sleep summary and analysis after each session
- IoT-based data collection and monitoring

---

## System Architecture

### Hardware Components
- Arduino Uno
- Pulse Sensor
- ECG Sensor
- Buzzer / Alarm module
- Computer for ML processing

### Software Components
- Arduino IDE
- Python
- Machine Learning libraries
- Python GUI

---

## Working Principle

### Mode 1: Pulse Sensor Based Detection
In this mode, the system monitors the user’s heart rate using a pulse sensor connected to the Arduino Uno.

- A **90-second average heart rate** is calculated.
- This average is used as a baseline to determine sleep or awake state.
- If the heart rate indicates the user is transitioning to an **awake/light sleep stage**, the alarm is triggered.

Accuracy observed during controlled testing: **~84.4%**

---

### Mode 2: ML Based Sleep Stage Detection
Mode 2 introduces **Machine Learning and ECG data analysis**.

- ECG signals are collected using an ECG sensor.
- Extracted features are fed into a trained ML classification model.
- The model predicts sleep stages and their duration.
- When the model detects a suitable wake-up stage, the alarm is triggered.

**ML Model Performance**
- Training data: 80%
- Testing data: 20%
- Model confidence: ~97%
- Real-world estimated accuracy: **85–90%**

---

## Technologies Used

### Hardware
- Arduino Uno
- Pulse Sensor
- ECG Sensor

### Software
- Arduino IDE
- Python
- Machine Learning algorithms
- GUI development

### Concepts
- Internet of Things (IoT)
- Heart Rate Analysis
- Sleep Stage Detection
- Data Classification

---

## Project Workflow

1. Sensors collect heart rate and ECG data.
2. Arduino processes and sends the data.
3. Data is analyzed using either:
   - Threshold-based method (Mode 1)
   - Machine Learning model (Mode 2)
4. Sleep stage is detected.
5. Alarm triggers at optimal wake-up time.
6. Sleep summary is displayed in the GUI.

---

## Results

| Mode | Method | Accuracy |
|-----|------|------|
| Mode 1 | Pulse sensor threshold detection | 84.4% |
| Mode 2 | ML-based ECG classification | 85–90% (real testing) |

---

## Future Improvements
- Integration with a mobile application
- Cloud-based sleep data storage
- Improved ML models for higher accuracy
- Wearable device integration
- Advanced sleep analytics dashboard

---

## Keywords
IoT, Machine Learning, Arduino, Pulse Sensor, ECG Sensor, Sleep Monitoring, Heart Rate Analysis, Smart Alarm

---

## Author
**Krishna Kumar**
