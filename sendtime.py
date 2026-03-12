import serial
import time
from datetime import datetime

# --- Adjust COM port and baud rate as needed ---
arduino = serial.Serial('COM7', 115200, timeout=1)
time.sleep(2)  # Wait for Arduino to reset

print("✅ Connected to Arduino on COM7. Sending time every second...")

try:
    while True:
        # Get current time in HH:MM format
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        # Send to Arduino
        arduino.write((current_time + "\n").encode())

        time.sleep(1)  # send every 1 second

except KeyboardInterrupt:
    print("\n🛑 Stopped by user.")
    arduino.close()
