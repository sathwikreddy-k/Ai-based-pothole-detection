import os
import cv2
import serial
import time
import folium
import threading
import webbrowser
import random
import queue
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from datetime import datetime
from ultralytics import YOLO

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'pothole.pt')
DATA_FILE = os.path.join(BASE_DIR, 'potholes.txt')
MAP_FILE = os.path.join(BASE_DIR, 'multiple_locations.html')
SERIAL_PORT = '/dev/ttyUSB0'  
BAUD_RATE = 9600
BASE_LAT, BASE_LON = 17.3222639, 78.5363244

class PotholeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Pothole Detection System")
        self.root.geometry("1200x800")
        self.root.configure(bg="#121212")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # State Variables
        self.current_gps = {"lat": BASE_LAT, "lon": BASE_LON, "time": "No Fix"}
        self.pothole_count = 0
        self.last_log_time = 0
        self.running = True
        self.map_lock = threading.Lock()
        
        # Thread-safe variables
        self.active_gps_mode = "Simulate"
        self.map_queue = queue.Queue()
        self.conf_threshold = tk.DoubleVar(value=0.3)

        self.setup_ui()
        
        print("Loading Model...")
        try:
            self.model = YOLO(MODEL_PATH)
        except Exception as e:
            print(f"Model Load Error: {e}")
            self.model = None
            
        self.cap = cv2.VideoCapture(0)
        
        # Start Backend Threads
        threading.Thread(target=self.gps_worker, daemon=True).start()
        threading.Thread(target=self.map_worker, daemon=True).start()
        self.process_loop()

    def setup_ui(self):
        sidebar = tk.Frame(self.root, width=300, bg="#1e1e26")
        sidebar.pack(side="left", fill="y")

        tk.Label(sidebar, text="CONTROLS", fg="#00d1b2", bg="#1e1e26", font=("Arial", 14, "bold")).pack(pady=20)

        # GPS Mode Selection
        tk.Label(sidebar, text="GPS Input:", fg="white", bg="#1e1e26").pack(anchor="w", padx=20)
        self.mode_combo = ttk.Combobox(sidebar, values=["Live", "Simulate", "Off"], state="readonly")
        self.mode_combo.set("Simulate")
        self.mode_combo.pack(fill="x", padx=20, pady=5)
        self.mode_combo.bind("<<ComboboxSelected>>", lambda e: setattr(self, 'active_gps_mode', self.mode_combo.get()))

        # Confidence Slider
        tk.Label(sidebar, text="Confidence:", fg="white", bg="#1e1e26").pack(anchor="w", padx=20, pady=(10,0))
        tk.Scale(sidebar, from_=0.1, to=1.0, resolution=0.05, orient="horizontal", variable=self.conf_threshold, bg="#1e1e26", fg="white").pack(fill="x", padx=20)

        # Action Buttons
        tk.Button(sidebar, text="Open Web Map", command=self.open_map, bg="#3498db", fg="white", font=("Arial", 10, "bold")).pack(fill="x", padx=20, pady=20)
        tk.Button(sidebar, text="Clear Session Data", command=self.clear_data, bg="#e67e22", fg="white").pack(fill="x", padx=20, pady=5)

        # Status Indicators
        self.status_label = tk.Label(sidebar, text="GPS: Waiting...", fg="#f1c40f", bg="#1e1e26", font=("Courier", 9), justify="left")
        self.status_label.pack(side="bottom", pady=10, padx=10)
        self.count_label = tk.Label(sidebar, text="Detected: 0", fg="#e74c3c", bg="#1e1e26", font=("Arial", 16, "bold"))
        self.count_label.pack(side="bottom", pady=10)

        # Main Video Panel
        self.video_panel = tk.Label(self.root, bg="black")
        self.video_panel.pack(side="right", expand=True, fill="both", padx=10, pady=10)

    def gps_worker(self):
        ser = None
        while self.running:
            mode = self.active_gps_mode
            if mode == "Simulate":
                lat_off, lon_off = random.uniform(-0.0005, 0.0005), random.uniform(-0.0005, 0.0005)
                self.current_gps.update({
                    "lat": round(BASE_LAT + lat_off, 7), 
                    "lon": round(BASE_LON + lon_off, 7), 
                    "time": datetime.now().strftime("%H:%M:%S")
                })
            elif mode == "Live":
                try:
                    if ser is None: ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if '$GPRMC' in line:
                        p = line.split(',')
                        if len(p) >= 6 and p[3] and p[5]:
                            self.current_gps["lat"] = round(float(p[3][:2]) + (float(p[3][2:]) / 60), 7)
                            self.current_gps["lon"] = round(float(p[5][:3]) + (float(p[5][3:]) / 60), 7)
                            self.current_gps["time"] = datetime.now().strftime("%H:%M:%S")
                except: 
                    self.current_gps["time"] = "Serial Error"
            time.sleep(1)

    def map_worker(self):
        while self.running:
            try:
                lat, lon = self.map_queue.get(timeout=1)
                self.update_map_file(lat, lon)
                self.map_queue.task_done()
            except queue.Empty:
                continue

    def update_map_file(self, lat, lon):
        with self.map_lock:
            try:
                m = folium.Map(location=[lat, lon], zoom_start=18)
                # Browser auto-refresh every 2 seconds
                m.get_root().header.add_child(folium.Element('<meta http-equiv="refresh" content="2">'))

                if os.path.exists(DATA_FILE):
                    with open(DATA_FILE, "r") as f:
                        lines = f.readlines()
                    
                    total = len(lines)
                    for i, line in enumerate(lines):
                        parts = line.strip().split(',')
                        if len(parts) >= 3:
                            try:
                                p_lat, p_lon = float(parts[0]), float(parts[1])
                                is_latest = (i == total - 1)
                                color = 'red' if is_latest else 'blue'
                                icon = 'info-sign' if is_latest else 'cloud'
                                
                                folium.Marker(
                                    [p_lat, p_lon], 
                                    popup=parts[2].strip('"'),
                                    icon=folium.Icon(color=color, icon=icon)
                                ).add_to(m)
                            except ValueError: continue
                m.save(MAP_FILE)
            except Exception as e: print(f"Map Error: {e}")

    def process_loop(self):
        ret, frame = self.cap.read()
        if ret and self.model:
            results = self.model.predict(frame, conf=self.conf_threshold.get(), verbose=False)
            if len(results[0].boxes) > 0 and (time.time() - self.last_log_time > 3) and self.active_gps_mode != "Off":
                self.pothole_count += 1
                self.last_log_time = time.time()
                lat, lon = self.current_gps["lat"], self.current_gps["lon"]
                
                # Log to file and trigger map update
                entry = f"{lat}, {lon}, \"{self.current_gps['time']}: Pothole\"\n"
                with open(DATA_FILE, "a") as f: f.write(entry)
                self.map_queue.put((lat, lon))
                self.count_label.config(text=f"Detected: {self.pothole_count}")

            self.status_label.config(text=f"LAT: {self.current_gps['lat']}\nLON: {self.current_gps['lon']}\nTIME: {self.current_gps['time']}")
            self.display_frame(results[0].plot())

        if self.running:
            self.root.after(20, self.process_loop)

    def display_frame(self, img):
        img_rgb = cv2.cvtColor(cv2.resize(img, (800, 600)), cv2.COLOR_BGR2RGB)
        img_tk = ImageTk.PhotoImage(Image.fromarray(img_rgb))
        self.video_panel.imgtk = img_tk
        self.video_panel.configure(image=img_tk)

    def open_map(self):
        if os.path.exists(MAP_FILE):
            webbrowser.open("file://" + os.path.abspath(MAP_FILE))

    def clear_data(self):
        """Clears logs, resets counter, and refreshes the map."""
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to delete all session logs and reset the counter?"):
            with open(DATA_FILE, "w") as f: f.write("") # Wipe file
            self.pothole_count = 0
            self.count_label.config(text="Detected: 0")
            self.update_map_file(BASE_LAT, BASE_LON) # Refresh clean map
            print("Session data cleared.")

    def on_closing(self):
        self.running = False
        if self.cap.isOpened(): self.cap.release()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = PotholeApp(root)
    root.mainloop()
