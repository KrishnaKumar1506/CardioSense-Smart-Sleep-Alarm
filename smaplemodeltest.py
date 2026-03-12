# import numpy as np
# import joblib

# # 1. Load the trained model
# model_path = "sleep_stage_rf_model.pkl"
# loaded_model = joblib.load(model_path)
# print("✅ Model loaded from:", model_path)

# # 2. Prepare input features for prediction
# # Example values (you should replace these with your actual measurements)
# ecg_value = 0.123   # example: some ECG reading
# bpm = 75.0    # beats per minute
# hrv = 30.2    # heart rate variability
# ecg_mean = 0.105   # mean of ECG signal
# ecg_std = 0.015   # standard deviation of ECG signal
# bpm_range = 20.0    # the range of bpm over some interval
# # energy of the signal (whatever your calculation defines)
# signal_energy = 1.234

# # Build the feature array in the same order as training
# feature_array = np.array([[ecg_value,
#                            bpm,
#                            hrv,
#                            ecg_mean,
#                            ecg_std,
#                            bpm_range,
#                            signal_energy]])

# # 3. Use the model to predict
# predicted_label = loaded_model.predict(feature_array)[0]
# print("🧠 Predicted label (sleep stage):", predicted_label)

# # 4. (Optional) If you have a probability or confidence, you might also call:
# if hasattr(loaded_model, "predict_proba"):
#     proba = loaded_model.predict_proba(feature_array)[0]
#     print("Predicted probabilities:", proba)



# import pandas as pd
# import joblib
# import numpy as np

# loaded_model = joblib.load("sleep_stage_rf_model.pkl")

# # Build a DataFrame for the new sample with proper column names
# col_names = ["ecg_value", "bpm", "hrv", "ecg_mean",
#              "ecg_std", "bpm_range", "signal_energy"]
# # Example values (you will supply actual)
# values = [0.123, 75.0, 30.2, 0.105, 0.015, 20.0, 1.234]

# sample_df = pd.DataFrame([values], columns=col_names)

# predicted_label = loaded_model.predict(sample_df)[0]
# print("Predicted label:", predicted_label)

"""
ecg_sleep_gui_threaded.py

Threaded Tkinter GUI for ECG sleep-stage monitoring.
- SerialReader thread reads Arduino -> pushes lines to queue
- Main thread parses lines, computes features, predicts label
- MonitorThread handles monitoring lifecycle (durations, 30s avg checks, light-30s alarm)
- Two-way serial for buzzer (BEEP_ON / BEEP_OFF)
- GUI is responsive (no blocking), styled with colors
"""

import numpy as np
import serial.tools.list_ports
import serial
import threading
from tkinter import ttk, messagebox
import tkinter as tk
from datetime import datetime
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import os
import sys
import time
import queue
import pandas as pd
import joblib

plt.rcParams["toolbar"] = "None"

# ---------------- CONFIG ----------------
COM_PORT_DEFAULT = "COM7"
BAUDRATE = 115200
MODEL_PATH = "sleep_stage_rf_model.pkl"

ECG_SAMPLE_RATE = 100.0        # approx (Hz)
FEATURE_WINDOW_SECONDS = 10    # for ecg mean/std/energy
BPM_WINDOW_SECONDS = 30        # window for avg and range
LIGHT_TRIGGER_SECONDS = 30     # continuous light seconds to trigger buzzer
AVG_UPDATE_INTERVAL = 30       # compute avg every 30 seconds

COL_NAMES = ["ecg_value", "bpm", "hrv", "ecg_mean",
             "ecg_std", "bpm_range", "signal_energy"]

# ---------------- Load model ----------------
try:
    loaded_model = joblib.load(MODEL_PATH)
except Exception as e:
    loaded_model = None
    print(f"Warning: Could not load model '{MODEL_PATH}': {e}")

# ---------------- Serial Reader ----------------


class SerialReader(threading.Thread):
    def __init__(self, port, baudrate, out_queue, stop_event):
        super().__init__(daemon=True)
        self.port = port
        self.baudrate = baudrate
        self.out_queue = out_queue
        self.stop_event = stop_event
        self.ser = None

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # give Arduino time to reset
            self.out_queue.put(
                ("info", f"Serial opened {self.port} @ {self.baudrate}"))
        except Exception as e:
            self.out_queue.put(("error", f"Cannot open {self.port}: {e}"))
            return

        try:
            while not self.stop_event.is_set():
                try:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                except Exception:
                    continue
                if line:
                    self.out_queue.put(("line", line))
        finally:
            try:
                self.ser.close()
            except:
                pass
            self.out_queue.put(("info", "Serial closed"))

    def write(self, text):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(text.encode('utf-8') + b'\n')
            except Exception as e:
                self.out_queue.put(("error", f"Serial write error: {e}"))

# ---------------- Monitor Thread ----------------


class MonitorThread(threading.Thread):
    """
    Runs while monitoring_active is True.
    - Increments durations every second for the current stage (thread-safe)
    - Tracks continuous 'light' duration and triggers buzzer if needed
    - Every AVG_UPDATE_INTERVAL, computes avg30s bpm/hrv and triggers safety buzzer if thresholds
    Communicates with main thread via shared state dict and lock.
    """

    def __init__(self, shared_state, shared_lock, serial_thread, stop_event, ui_queue):
        super().__init__(daemon=True)
        self.shared_state = shared_state
        self.shared_lock = shared_lock
        self.serial_thread = serial_thread
        self.stop_event = stop_event  # used to stop thread when app closes
        self.ui_queue = ui_queue  # to notify GUI for changes/messages
        self._running = threading.Event()

    def start_monitoring(self):
        self._running.set()
        if not self.is_alive():
            self.start()

    def stop_monitoring(self):
        self._running.clear()

    def run(self):
        last_second = time.time()
        last_avg = time.time()
        while not self.stop_event.is_set():
            if not self._running.is_set():
                time.sleep(0.1)
                continue

            now = time.time()
            # increment durations every 1 second
            if now - last_second >= 1.0:
                last_second = now
                with self.shared_lock:
                    current_stage = self.shared_state.get("current_stage")
                    if current_stage in self.shared_state["durations"]:
                        self.shared_state["durations"][current_stage] += 1
                # send UI update request
                self.ui_queue.put(("update_durations", None))

            # check light-continuous alarm (must be inside alarm window)
            with self.shared_lock:
                in_alarm = self.shared_state.get("in_alarm_window", False)
                stage = self.shared_state.get("current_stage")
                light_start = self.shared_state.get("light_continuous_start")
                buzzer_forced = self.shared_state.get(
                    "buzzer_forced_on", False)
                buzzer_on_flag = self.shared_state.get("buzzer_on", False)

            if in_alarm and stage == "light":
                if light_start is None:
                    with self.shared_lock:
                        self.shared_state["light_continuous_start"] = now
                else:
                    elapsed_light = now - light_start
                    if elapsed_light >= LIGHT_TRIGGER_SECONDS and not buzzer_on_flag:
                        # trigger buzzer ON
                        if self.serial_thread:
                            self.serial_thread.write("BEEP_ON")
                        with self.shared_lock:
                            self.shared_state["buzzer_on"] = True
                            self.shared_state["buzzer_forced_on"] = True
                        self.ui_queue.put(("buzzer_changed", True))
            else:
                # reset light timer if stage not light or not in alarm
                if light_start is not None and (stage != "light" or not in_alarm):
                    with self.shared_lock:
                        self.shared_state["light_continuous_start"] = None

            # every AVG_UPDATE_INTERVAL seconds compute average bpm/hrv
            if now - last_avg >= AVG_UPDATE_INTERVAL:
                last_avg = now
                with self.shared_lock:
                    bpm_vals = [v for (
                        t, v) in self.shared_state["bpm_buffer"] if t >= now - BPM_WINDOW_SECONDS]
                    hrv_vals = [v for (
                        t, v) in self.shared_state["hrv_buffer"] if t >= now - BPM_WINDOW_SECONDS]
                avg_bpm = float(np.mean(bpm_vals)) if bpm_vals else None
                avg_hrv = float(np.mean(hrv_vals)) if hrv_vals else None
                with self.shared_lock:
                    self.shared_state["avg_bpm_30"] = avg_bpm
                    self.shared_state["avg_hrv_30"] = avg_hrv

                # safety check
                if avg_bpm is not None:
                    if avg_bpm > 100:
                        # trigger buzzer + warning
                        if self.serial_thread:
                            self.serial_thread.write("BEEP_ON")
                        with self.shared_lock:
                            self.shared_state["buzzer_on"] = True
                            self.shared_state["bpm_safety_triggered"] = True
                            self.shared_state["warning_text"] = "BPM TOO HIGH"
                        self.ui_queue.put(("warning", "BPM TOO HIGH"))
                        self.ui_queue.put(("buzzer_changed", True))
                    elif avg_bpm < 40:
                        if self.serial_thread:
                            self.serial_thread.write("BEEP_ON")
                        with self.shared_lock:
                            self.shared_state["buzzer_on"] = True
                            self.shared_state["bpm_safety_triggered"] = True
                            self.shared_state["warning_text"] = "BPM TOO LOW"
                        self.ui_queue.put(("warning", "BPM TOO LOW"))
                        self.ui_queue.put(("buzzer_changed", True))
                    else:
                        # clear safety if previously triggered
                        with self.shared_lock:
                            if self.shared_state.get("bpm_safety_triggered"):
                                if self.serial_thread:
                                    self.serial_thread.write("BEEP_OFF")
                                self.shared_state["buzzer_on"] = False
                                self.shared_state["bpm_safety_triggered"] = False
                                self.shared_state["warning_text"] = ""
                                self.ui_queue.put(("warning_clear", None))
                                self.ui_queue.put(("buzzer_changed", False))

                # notify UI to refresh avg labels
                self.ui_queue.put(("avg_update", None))

            time.sleep(0.15)

# ---------------- Main GUI App ----------------


class ECGApp:
    def __init__(self, root):
        self.root = root
        root.title("ECG Sleep Stage Monitor (Threaded)")
        root.geometry("1050x720")
        # styling
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure("TFrame", background="#f4f6fb")
        style.configure("TLabel", background="#f4f6fb", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Warning.TLabel", foreground="red",
                        font=("Segoe UI", 12, "bold"))
        style.configure("Green.TLabel", foreground="green",
                        font=("Segoe UI", 11, "bold"))

        # queues and threads
        self.serial_q = queue.Queue()
        self.ui_q = queue.Queue()
        self.serial_stop_event = threading.Event()
        self.serial_thread = None

        self.monitor_thread = None

        # shared state protected by lock
        self.shared_lock = threading.Lock()
        self.shared_state = {
            "current_stage": None,
            "durations": {"awake": 0, "light": 0, "deep": 0},
            "bpm_buffer": [],  # holds (ts, bpm)
            "hrv_buffer": [],  # holds (ts, hrv)
            "avg_bpm_30": None,
            "avg_hrv_30": None,
            "light_continuous_start": None,
            "buzzer_on": False,
            "buzzer_forced_on": False,
            "bpm_safety_triggered": False,
            "warning_text": "",
            "in_alarm_window": False,
        }

        # GUI variables
        self.com_var = tk.StringVar(value=COM_PORT_DEFAULT)
        self.alarm_start = tk.StringVar(value="07:00")
        self.alarm_end = tk.StringVar(value="07:30")
        self.alarm_enabled = tk.BooleanVar(value=True)
        self.monitoring_active = False

        # live values
        self.ecg_value_var = tk.StringVar(value="-")
        self.bpm_var = tk.StringVar(value="-")
        self.hrv_var = tk.StringVar(value="-")
        self.stage_var = tk.StringVar(value="-")
        self.avg_bpm_var = tk.StringVar(value="-")
        self.avg_hrv_var = tk.StringVar(value="-")
        self.buzzer_var = tk.StringVar(value="OFF")
        self.warning_var = tk.StringVar(value="")

        self._build_gui()
        self._init_plot()

        # start a periodic UI poll to handle serial lines & UI queue
        self.root.after(100, self._periodic)

    def _build_gui(self):
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=12, pady=8)

        ttk.Label(top, text="ECG Sleep Monitor",
                  style="Title.TLabel").pack(side="left")

        # right-side controls on top
        controls = ttk.Frame(self.root)
        controls.pack(fill="x", padx=12)

        row1 = ttk.Frame(controls)
        row1.pack(fill="x", pady=4)
        ttk.Label(row1, text="COM:").pack(side="left")
        self.combobox = ttk.Combobox(row1, textvariable=self.com_var, width=12)
        self.combobox['values'] = self._list_ports()
        self.combobox.pack(side="left", padx=6)
        ttk.Button(row1, text="Refresh", command=self._refresh_ports).pack(
            side="left", padx=4)
        self.start_serial_btn = ttk.Button(
            row1, text="Start Serial", command=self._start_serial)
        self.start_serial_btn.pack(side="left", padx=6)
        self.stop_serial_btn = ttk.Button(
            row1, text="Stop Serial", command=self._stop_serial, state="disabled")
        self.stop_serial_btn.pack(side="left", padx=6)

        # Alarm window
        alarm_frame = ttk.LabelFrame(self.root, text="Alarm Window (HH:MM)")
        alarm_frame.pack(fill="x", padx=12, pady=6)
        ttk.Checkbutton(alarm_frame, text="Enable",
                        variable=self.alarm_enabled).pack(side="left", padx=6)
        ttk.Label(alarm_frame, text="Start").pack(side="left")
        ttk.Entry(alarm_frame, textvariable=self.alarm_start,
                  width=6).pack(side="left", padx=6)
        ttk.Label(alarm_frame, text="End").pack(side="left")
        ttk.Entry(alarm_frame, textvariable=self.alarm_end,
                  width=6).pack(side="left", padx=6)

        # Monitoring controls
        mon_frame = ttk.Frame(self.root)
        mon_frame.pack(fill="x", padx=12, pady=6)
        self.start_monitor_btn = ttk.Button(
            mon_frame, text="Start Monitoring", command=self._start_monitoring)
        self.start_monitor_btn.pack(side="left", padx=6)
        self.stop_monitor_btn = ttk.Button(
            mon_frame, text="Stop Monitoring", command=self._stop_monitoring, state="disabled")
        self.stop_monitor_btn.pack(side="left", padx=6)
        ttk.Button(mon_frame, text="Manual BEEP ON", command=lambda: self._manual_buzzer(
            True)).pack(side="left", padx=6)
        ttk.Button(mon_frame, text="Manual BEEP OFF", command=lambda: self._manual_buzzer(
            False)).pack(side="left", padx=6)
        ttk.Button(mon_frame, text="Show Durations",
                   command=self._show_durations).pack(side="right", padx=6)

        # Info labels
        info_frame = ttk.Frame(self.root)
        info_frame.pack(fill="x", padx=12, pady=6)

        def label_box(title, var, width=14):
            f = ttk.Frame(info_frame)
            f.pack(side="left", padx=8)
            ttk.Label(f, text=title).pack()
            lbl = ttk.Label(f, textvariable=var, style="Green.TLabel")
            lbl.config(width=width, anchor="center")
            lbl.pack()
            return lbl

        self.ecg_lbl = label_box("ECG", self.ecg_value_var, width=10)
        self.bpm_lbl = label_box("BPM", self.bpm_var, width=8)
        self.hrv_lbl = label_box("HRV", self.hrv_var, width=8)
        self.avg_bpm_lbl = label_box("Avg30s BPM", self.avg_bpm_var, width=10)
        self.avg_hrv_lbl = label_box("Avg30s HRV", self.avg_hrv_var, width=10)
        self.stage_lbl = label_box("Stage", self.stage_var, width=10)
        self.buzzer_lbl = label_box("Buzzer", self.buzzer_var, width=8)

        # Warning
        self.warning_label = ttk.Label(
            self.root, textvariable=self.warning_var, style="Warning.TLabel")
        self.warning_label.pack(pady=4)

        # Plot area
        plot_frame = ttk.Frame(self.root)
        plot_frame.pack(fill="both", expand=True, padx=12, pady=8)
        self.fig, self.ax = plt.subplots(figsize=(10, 3))
        self.line, = self.ax.plot([], [])
        self.ax.set_ylabel("Normalized ECG")
        self.ax.set_xlabel("Seconds (recent)")
        self.ax.set_xlim(-FEATURE_WINDOW_SECONDS, 0)
        self.ax.set_ylim(-0.2, 1.2)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # bottom status
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            self.root, textvariable=self.status_var, anchor="w")
        status_bar.pack(fill="x", padx=12, pady=6)

    def _init_plot(self):
        self.plot_x = np.linspace(-FEATURE_WINDOW_SECONDS,
                                  0, int(FEATURE_WINDOW_SECONDS * ECG_SAMPLE_RATE))
        self.plot_y = np.zeros_like(self.plot_x)
        self.line.set_data(self.plot_x, self.plot_y)
        self.canvas.draw_idle()

    # ---------------- Serial control ----------------
    def _list_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]

    def _refresh_ports(self):
        self.combobox['values'] = self._list_ports()

    def _start_serial(self):
        port = self.com_var.get().strip()
        if not port:
            messagebox.showerror("Error", "Select COM port")
            return
        if self.serial_thread and self.serial_thread.is_alive():
            messagebox.showinfo("Info", "Serial already running")
            return
        self.serial_stop_event.clear()
        self.serial_thread = SerialReader(
            port, BAUDRATE, self.serial_q, self.serial_stop_event)
        self.serial_thread.start()
        self.start_serial_btn.config(state="disabled")
        self.stop_serial_btn.config(state="normal")
        self.status_var.set(f"Serial running on {port}")

    def _stop_serial(self):
        if self.serial_thread:
            self.serial_stop_event.set()
            self.serial_thread = None
        self.start_serial_btn.config(state="normal")
        self.stop_serial_btn.config(state="disabled")
        self.status_var.set("Serial stopped")

    # ---------------- Monitoring control ----------------
    def _start_monitoring(self):
        if not self.serial_thread:
            messagebox.showwarning("Serial not running",
                                   "Start the serial connection first.")
            return
        if self.monitoring_active:
            return

        # prepare shared state
        with self.shared_lock:
            self.shared_state["durations"] = {
                "awake": 0, "light": 0, "deep": 0}
            self.shared_state["bpm_buffer"] = list(
                self.shared_state.get("bpm_buffer", []))
            self.shared_state["hrv_buffer"] = list(
                self.shared_state.get("hrv_buffer", []))
            self.shared_state["avg_bpm_30"] = None
            self.shared_state["avg_hrv_30"] = None
            self.shared_state["light_continuous_start"] = None
            self.shared_state["buzzer_forced_on"] = False
            self.shared_state["buzzer_on"] = False
            self.shared_state["bpm_safety_triggered"] = False
            self.shared_state["warning_text"] = ""
            # set alarm window flag initially
            self.shared_state["in_alarm_window"] = self._is_in_alarm_window()

        # create monitor thread if needed
        if self.monitor_thread is None:
            self.monitor_thread = MonitorThread(
                self.shared_state, self.shared_lock, self.serial_thread, self.serial_stop_event, self.ui_q)
        self.monitor_thread.start_monitoring()
        self.monitoring_active = True
        self.start_monitor_btn.config(state="disabled")
        self.stop_monitor_btn.config(state="normal")
        self.status_var.set("Monitoring started")
        # start a small UI push so the monitor knows the in_alarm_window
        self._update_alarm_window_flag()

    def _stop_monitoring(self):
        if not self.monitoring_active:
            return
        if self.monitor_thread:
            self.monitor_thread.stop_monitoring()
        self.monitoring_active = False
        self.start_monitor_btn.config(state="normal")
        self.stop_monitor_btn.config(state="disabled")
        self.status_var.set("Monitoring stopped manually")
        # show summary and reset durations
        self._show_and_reset_durations("Monitoring stopped")

    def _manual_buzzer(self, on):
        if not self.serial_thread:
            messagebox.showwarning("Serial not running", "Start serial first")
            return
        self.serial_thread.write("BEEP_ON" if on else "BEEP_OFF")
        with self.shared_lock:
            self.shared_state["buzzer_on"] = on
        self.buzzer_var.set("ON" if on else "OFF")
        self.status_var.set("Manual buzzer " + ("ON" if on else "OFF"))

    # ---------------- Serial & parsing ----------------
    def _periodic(self):
        # handle serial queue
        try:
            while not self.serial_q.empty():
                typ, payload = self.serial_q.get_nowait()
                if typ == "line":
                    self._handle_line(payload)
                elif typ == "info":
                    self.status_var.set(payload)
                elif typ == "error":
                    messagebox.showerror("Serial Error", payload)
        except queue.Empty:
            pass

        # handle UI queue messages from monitor thread
        try:
            while not self.ui_q.empty():
                typ, payload = self.ui_q.get_nowait()
                if typ == "update_durations":
                    # update summary labels
                    self._refresh_duration_label()
                elif typ == "buzzer_changed":
                    # payload True = ON, False = OFF (or None)
                    with self.shared_lock:
                        on_flag = self.shared_state.get("buzzer_on", False)
                    self.buzzer_var.set("ON" if on_flag else "OFF")
                elif typ == "warning":
                    self.warning_var.set(payload)
                elif typ == "warning_clear":
                    self.warning_var.set("")
                elif typ == "avg_update":
                    with self.shared_lock:
                        avg_b = self.shared_state.get("avg_bpm_30")
                        avg_h = self.shared_state.get("avg_hrv_30")
                    self.avg_bpm_var.set(
                        f"{avg_b:.1f}" if avg_b is not None else "-")
                    self.avg_hrv_var.set(
                        f"{avg_h:.1f}" if avg_h is not None else "-")
        except queue.Empty:
            pass

        # normal GUI periodic tasks
        self._update_plot()
        # update alarm window flag
        self._update_alarm_window_flag()

        # schedule next
        self.root.after(100, self._periodic)

    def _handle_line(self, line):
        # expected lines: ECG:<int>, BPM:<val> HRV:<val>, or "!"
        if line == "!":
            self.ecg_value_var.set("LEAD-OFF")
            return

        if line.startswith("ECG:"):
            try:
                val = int(line.split("ECG:")[1].strip())
            except:
                return
            norm = max(0.0, min(1.0, val / 1023.0))
            ts = time.time()
            # maintain ecg buffer in shared_state? We'll keep local copy for plotting & feature calc
            # but store current ecg and features in shared_state for monitor thread if needed
            with self.shared_lock:
                # append to an ecg_buffer in shared_state for feature calc (kept trimmed)
                buf = self.shared_state.get("ecg_buffer", [])
                buf.append((ts, norm))
                cutoff = ts - FEATURE_WINDOW_SECONDS
                buf = [p for p in buf if p[0] >= cutoff]
                self.shared_state["ecg_buffer"] = buf
                # update last ecg value for UI
                self.shared_state["last_ecg"] = norm
            self.ecg_value_var.set(f"{norm:.3f}")
        elif "BPM:" in line:
            try:
                parts = line.split()
                bpm_val = None
                hrv_val = None
                for p in parts:
                    if p.startswith("BPM:"):
                        bpm_val = float(p.split("BPM:")[1])
                    if p.startswith("HRV:"):
                        hrv_val = float(p.split("HRV:")[1])
                ts = time.time()
                with self.shared_lock:
                    if bpm_val is not None:
                        buf = self.shared_state.get("bpm_buffer", [])
                        buf.append((ts, bpm_val))
                        # keep last 2*BPM_WINDOW_SECONDS for safety
                        buf = [p for p in buf if p[0] >=
                               ts - BPM_WINDOW_SECONDS * 2]
                        self.shared_state["bpm_buffer"] = buf
                        self.shared_state["last_bpm"] = bpm_val
                        self.bpm_var.set(f"{bpm_val:.0f}")
                    if hrv_val is not None:
                        bufh = self.shared_state.get("hrv_buffer", [])
                        bufh.append((ts, hrv_val))
                        bufh = [p for p in bufh if p[0] >=
                                ts - BPM_WINDOW_SECONDS * 2]
                        self.shared_state["hrv_buffer"] = bufh
                        self.shared_state["last_hrv"] = hrv_val
                        self.hrv_var.set(f"{hrv_val:.1f}")
            except Exception as e:
                print("Parse BPM error:", e)
        else:
            # unknown line - ignore
            pass

        # compute features & predict every time new data arrives (non-blocking)
        self._compute_features_and_predict()

    def _compute_features_and_predict(self):
        # gather ecg buffer and bpm/hrv last values from shared_state
        with self.shared_lock:
            ecg_buf = list(self.shared_state.get("ecg_buffer", []))
            bpm_buf = list(self.shared_state.get("bpm_buffer", []))
            hrv_buf = list(self.shared_state.get("hrv_buffer", []))
            last_bpm = self.shared_state.get("last_bpm", None)
            last_hrv = self.shared_state.get("last_hrv", None)

        if not ecg_buf:
            return

        ecg_vals = np.array([v for (_, v) in ecg_buf])
        ecg_value = float(ecg_vals[-1])
        ecg_mean = float(np.mean(ecg_vals))
        ecg_std = float(np.std(ecg_vals, ddof=0))
        bpm_val = float(last_bpm) if last_bpm is not None else 0.0
        hrv_val = float(last_hrv) if last_hrv is not None else 0.0

        if bpm_buf:
            now = time.time()
            recent_bpm_vals = np.array(
                [v for (t, v) in bpm_buf if t >= now - BPM_WINDOW_SECONDS])
            bpm_range = float(np.max(
                recent_bpm_vals) - np.min(recent_bpm_vals)) if recent_bpm_vals.size else 0.0
        else:
            bpm_range = 0.0

        signal_energy = float(np.sum(ecg_vals ** 2))

        sample_df = pd.DataFrame(
            [[ecg_value, bpm_val, hrv_val, ecg_mean, ecg_std, bpm_range, signal_energy]], columns=COL_NAMES)

        predicted_label = None
        if loaded_model is not None:
            try:
                predicted_label = loaded_model.predict(sample_df)[0]
            except Exception as e:
                print("Prediction error:", e)

        if predicted_label is not None:
            pl = str(predicted_label).lower()
            # map numeric labels if necessary
            if pl not in ("awake", "light", "deep"):
                if pl in ("0", "1", "2"):
                    mapping = {"0": "awake", "1": "light", "2": "deep"}
                    pl = mapping.get(pl, pl)
            with self.shared_lock:
                self.shared_state["current_stage"] = pl
        else:
            with self.shared_lock:
                self.shared_state["current_stage"] = None

        # update UI stage label
        with self.shared_lock:
            stage_for_ui = self.shared_state.get("current_stage", None)
        self.stage_var.set(stage_for_ui.capitalize() if stage_for_ui else "-")

    # ---------------- UI helpers ----------------
    def _update_plot(self):
        with self.shared_lock:
            ecg_buf = list(self.shared_state.get("ecg_buffer", []))
        if not ecg_buf:
            return
        now_ts = time.time()
        xs = np.array([t - now_ts for (t, _) in ecg_buf])  # negative seconds
        ys = np.array([v for (_, v) in ecg_buf])
        self.line.set_data(xs, ys)
        self.ax.set_xlim(-FEATURE_WINDOW_SECONDS, 0)
        ymin = min(-0.2, float(np.min(ys) - 0.05))
        ymax = max(1.2, float(np.max(ys) + 0.05))
        self.ax.set_ylim(ymin, ymax)
        self.canvas.draw_idle()

    def _refresh_duration_label(self):
        with self.shared_lock:
            d = self.shared_state["durations"]
        # show in status bar
        self.status_var.set(
            f"Durations — Awake: {d['awake']}s  Light: {d['light']}s  Deep: {d['deep']}s")

    def _show_durations(self):
        with self.shared_lock:
            d = self.shared_state["durations"].copy()
        msg = f"Durations:\nAwake: {d['awake']} s\nLight: {d['light']} s\nDeep: {d['deep']} s"
        messagebox.showinfo("Durations", msg)

    def _show_and_reset_durations(self, title):
        with self.shared_lock:
            d = self.shared_state["durations"].copy()
            # reset
            self.shared_state["durations"] = {
                "awake": 0, "light": 0, "deep": 0}
            # reset light timer and warnings/buzzer flags
            self.shared_state["light_continuous_start"] = None
            # turn off buzzer if forced by monitor
            if self.shared_state.get("buzzer_on"):
                if self.serial_thread:
                    self.serial_thread.write("BEEP_OFF")
            self.shared_state["buzzer_on"] = False
            self.shared_state["buzzer_forced_on"] = False
            self.shared_state["bpm_safety_triggered"] = False
            self.shared_state["warning_text"] = ""
        # show popup
        messagebox.showinfo(
            "Monitoring Summary", f"{title}\n\nAwake: {d['awake']} s\nLight: {d['light']} s\nDeep: {d['deep']} s")
        self.status_var.set("Durations reset")

    def _is_in_alarm_window(self):
        if not self.alarm_enabled.get():
            return False
        try:
            start_t = datetime.strptime(self.alarm_start.get(), "%H:%M").time()
            end_t = datetime.strptime(self.alarm_end.get(), "%H:%M").time()
        except:
            return False
        nowt = datetime.now().time()
        if start_t <= end_t:
            return start_t <= nowt <= end_t
        else:
            return nowt >= start_t or nowt <= end_t

    def _update_alarm_window_flag(self):
        in_alarm = self._is_in_alarm_window()
        with self.shared_lock:
            prev = self.shared_state.get("in_alarm_window", False)
            self.shared_state["in_alarm_window"] = in_alarm
        # if alarm window ended while monitoring active, stop monitoring and show summary
        if prev and not in_alarm and self.monitoring_active:
            # alarm ended
            self._show_and_reset_durations("Alarm window ended")
            # stop monitor thread activity
            if self.monitor_thread:
                self.monitor_thread.stop_monitoring()
            self.monitoring_active = False
            self.start_monitor_btn.config(state="normal")
            self.stop_monitor_btn.config(state="disabled")

    # ---------------- Control callbacks ----------------
    def _start_monitoring(self):
        self._start_monitoring()  # placeholder - shouldn't be used directly

    def _start_monitoring(self):
        # wrapper to keep name unique
        if not self.serial_thread:
            messagebox.showwarning(
                "No Serial", "Start serial connection first.")
            return
        if self.monitoring_active:
            return
        # set monitoring flag and start monitor thread
        self.monitoring_active = True
        with self.shared_lock:
            self.shared_state["durations"] = {
                "awake": 0, "light": 0, "deep": 0}
            self.shared_state["light_continuous_start"] = None
            self.shared_state["buzzer_forced_on"] = False
            self.shared_state["bpm_safety_triggered"] = False
            self.shared_state["warning_text"] = ""
            self.shared_state["in_alarm_window"] = self._is_in_alarm_window()
        if self.monitor_thread is None:
            self.monitor_thread = MonitorThread(
                self.shared_state, self.shared_lock, self.serial_thread, self.serial_stop_event, self.ui_q)
        # ensure monitor has access to the current serial_thread object
        self.monitor_thread.serial_thread = self.serial_thread
        self.monitor_thread.start_monitoring()
        self.start_monitor_btn.config(state="disabled")
        self.stop_monitor_btn.config(state="normal")
        self.status_var.set("Monitoring started")

    def _stop_monitoring(self):
        if not self.monitoring_active:
            return
        if self.monitor_thread:
            self.monitor_thread.stop_monitoring()
        self.monitoring_active = False
        self.start_monitor_btn.config(state="normal")
        self.stop_monitor_btn.config(state="disabled")
        self._show_and_reset_durations("Monitoring stopped manually")

    def _manual_buzzer(self, on):
     if not self.serial_thread:
        messagebox.showwarning("Serial not running", "Start serial first")
        return

    # Send ON or OFF signal to Arduino
     self.serial_thread.write("BEEP_ON" if on else "BEEP_OFF")

    # Update internal state and GUI label
     with self.shared_lock:
        self.shared_state["buzzer_on"] = on
     self.buzzer_var.set("ON" if on else "OFF")

    # --- Auto turn off after if manually turned ON ---
     if on:
        def auto_off():
            self.serial_thread.write("BEEP_OFF")
            with self.shared_lock:
                self.shared_state["buzzer_on"] = False
            self.buzzer_var.set("OFF")

        # Schedule auto-off after some duration
        self.root.after(7000, auto_off)


    # ---------------- App close ----------------
    def on_close(self):
        if self.monitoring_active:
            if not messagebox.askyesno("Exit", "Monitoring is active. Stop and exit?"):
                return
        # stop monitor thread
        if self.monitor_thread:
            self.monitor_thread.stop_monitoring()
        # stop serial thread
        if self.serial_thread:
            self.serial_stop_event.set()
        self.root.after(200, self.root.destroy)

# ---------------- Run ----------------


def main():
    root = tk.Tk()
    app = ECGApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
