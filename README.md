# AI Based Pothole Detection

Real-time pothole detection using a YOLO model, with GPS-tagged logging and a live web map of detected potholes.

## Features
- Live webcam detection with a custom-trained YOLO model (`pothole.pt`)
- GPS input: **Live** (serial NMEA `$GPRMC`), **Simulate**, or **Off**
- Adjustable confidence threshold
- Detections logged to `potholes.txt` (lat, lon, time)
- Auto-refreshing Folium map (`multiple_locations.html`) with the latest pothole in red
- Tkinter dashboard with detection counter

## Setup
```bash
git clone https://github.com/<your-username>/pothole-detection.git
cd pothole-detection
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run
```bash
python detect.py
```
Edit `SERIAL_PORT` / `BAUD_RATE` in `detect.py` for your GPS module (default `/dev/ttyUSB0`, 9600).

## Project structure
| File | Purpose |
|---|---|
| `detect.py` | Main app (detection, GPS, map, GUI) |
| `pothole.pt` | Trained YOLO weights |
| `potholes.txt` | Detection log (lat, lon, timestamp) |
