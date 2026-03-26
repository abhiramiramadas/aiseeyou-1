# 🚗 AI See You — Real-Time Accident Detection & Emergency Response

> **Every Second Counts, AI Makes It Faster**

A Python system that watches live video, detects vehicle collisions using YOLO, scores their severity, locates the nearest hospital and police station via OpenStreetMap, and fires off email alerts — all automatically.

---

## 📁 Repository Structure

```
aiseeyou/
├── main.py            # Entry point — CLI with --api / --video / --camera / --gui / --test modes
├── detection.py       # Core engine: AccidentDetector, VehicleTracker, SeverityCalculator, Flask API
├── alert.py           # AlertSystem: emergency email, nominee alert, blood donation, insurance claim
├── OSM.PY             # EmergencyServicesLocator + WeatherService (Overpass API + OpenWeatherMap)
├── config.py          # All thresholds, model paths, email credentials, GPS defaults
├── haversine_gui.py   # Tkinter GUI wrapper around Haversine + OSM hospital map
├── test_mail.py       # Standalone email test harness
├── uploads/           # Runtime folder — accident frames, clips, PDF reports saved here
├── Requirements.txt   # Python dependencies
└── logs.txt           # Runtime log output (UTF-8)
```

---

## ⚙️ How It Works

### 1. Detection (`detection.py`)

**`VehicleTracker`** maintains a `defaultdict` of tracks keyed by integer ID. On each frame it matches new detections to existing tracks by nearest centre-point distance (threshold: 100 px, max age: 30 frames), then computes speed as the average pixel-distance over the last 5 frames.

**`calculate_iou(boxA, boxB)`** computes Intersection over Union between two `[x1, y1, x2, y2]` bounding boxes with a small epsilon (`1e-6`) to avoid division by zero.

**`SeverityCalculator.calculate(iou, speed1, speed2, vehicle_types)`** produces an impact score (0–100) from three components:

| Component | Range | Logic |
|-----------|-------|-------|
| IoU score | 0–40 | `min(iou × 80, 40)` |
| Speed score | 0–40 | 40 / 25 / 15 / 5 based on `SPEED_HIGH/MED/LOW` thresholds |
| Vehicle type | 0–20 | +10 per heavy vehicle (Truck, Bus), capped at 20 |

A collision is only flagged if `iou > IOU_THRESHOLD_LOW` **and** `max(speed1, speed2) >= MIN_SPEED_FOR_ACCIDENT` — this prevents false positives from parked cars overlapping in the frame.

**`AccidentDetector`** ties everything together:
- Selects `yolov8n / yolov8s / yolov8m` dynamically based on available RAM (`psutil`)
- Runs YOLO at confidence `> 0.3` on 5 COCO vehicle classes (Car, Motorcycle, Bus, Truck, Bicycle)
- On collision: saves frame to `uploads/`, spawns a background thread for all alerts
- Enforces a 10-second cooldown between alerts for the same scene

**Flask API** (started via `python main.py --api`):

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web dashboard |
| GET | `/health` | Model status + feature flags |
| POST | `/detect` | Upload video, returns JSON accident list |
| GET | `/accidents` | All accidents detected this session |
| GET | `/stream` | MJPEG stream from webcam |
| GET | `/statistics` | Severity breakdown counts |
| GET | `/export/excel` | Download accidents as `.xlsx` |
| GET | `/export/map` | Interactive Leaflet map |

---

### 2. Emergency Services (`OSM.PY`)

**`haversine_distance(lat1, lon1, lat2, lon2)`** — pure Python implementation of the Haversine formula using `math.radians` and `math.atan2`. Returns km.

**`EmergencyServicesLocator`** queries the **Overpass API** (`https://overpass-api.de/api/interpreter`) for hospitals, police stations and fire stations within a configurable radius (default 5 km). It applies two filtering layers before returning results:

- **Exclusion keywords** — strips dental clinics, eye hospitals, vet centres, ayurvedic/homeopathic centres, dialysis units, nursing homes, physiotherapy, blood banks, etc.
- **Preference scoring** — up-ranks government hospitals, medical colleges, multi-speciality hospitals, and named chains (Apollo, Fortis, Lakeshore, Amrita, KIMS, etc.)

Results are sorted by `distance_km − (preference_score × 0.5)` so a well-known hospital 0.3 km further beats an unknown clinic.

**`WeatherService`** calls **OpenWeatherMap** and computes a risk factor (Low / Medium / High) from precipitation type, visibility, rainfall rate and wind speed. Falls back to a simulated "Clear, 28°C, Low risk" response if no API key is configured.

Default coordinates in `config.py`: **Kochi, Kerala** (`9.9312, 76.2673`).

---

### 3. Alert System (`alert.py`)

**`AlertSystem`** sends emails via `smtplib` over Gmail SMTP (`smtp.gmail.com:587`, STARTTLS). Four distinct email types:

**Emergency alert** (`send_accident_alert`) — sent to `EMERGENCY_CONTACTS`:
- Accident location with Google Maps link
- Severity, IoU, vehicle types, impact score
- Nearest hospital (name, distance, phone, address) + up to 2 more nearby hospitals
- Nearest police station
- Live weather conditions + risk factor
- Attaches accident frame image and optional video clip

**Nominee/family alert** (`send_nominee_alert`) — sent to `NOMINEE_CONTACTS` when severity is HIGH or CRITICAL. Includes the same hospital and police details plus a Google Maps link.

**Blood donation request** (`send_blood_donation_request`) — triggered only on CRITICAL severity. Asks nominees to go to the nearest hospital immediately.

**Insurance claim** (`send_insurance_claim`) — auto-generates a claim reference (`ACC-YYYYMMDDHHMMSS`), estimates repair cost and days using `DamageEstimator`, and returns the full claim dict as JSON in the email body.

`ENABLE_EMAIL_ALERTS = False` in `config.py` puts the system in simulation mode — it prints what would be sent without actually sending.

---

### 4. Configuration (`config.py`)

All values are read from **environment variables** with sensible defaults, so no secrets need to be hardcoded:

```python
SENDER_EMAIL   = os.getenv("SENDER_EMAIL", "...")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "...")   # Gmail App Password
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")

# IoU thresholds
IOU_THRESHOLD_LOW    = 0.30   # minimum to flag a collision
IOU_THRESHOLD_MEDIUM = 0.45
IOU_THRESHOLD_HIGH   = 0.60

# Speed thresholds (pixels/frame)
SPEED_LOW  = 15
SPEED_MED  = 30
SPEED_HIGH = 50
MIN_SPEED_FOR_ACCIDENT = 5    # stops parked-car false positives

# YOLO model selection by RAM
MODEL_PATHS = {
    "light":  "models/yolov8n.pt",   # < 4 GB
    "medium": "models/yolov8s.pt",   # 4–8 GB
    "heavy":  "models/yolov8m.pt",   # > 8 GB
}
```

---

## 🚀 Running the System

### Install dependencies
```bash
pip install -r Requirements.txt
```

### Download YOLO weights
```bash
mkdir models
# yolov8n.pt will auto-download on first run via ultralytics
```

### Set credentials
```bash
export SENDER_EMAIL="your@gmail.com"
export EMAIL_PASSWORD="your-app-password"   # Gmail App Password, not your login
export WEATHER_API_KEY="your-owm-key"       # optional, falls back to simulated weather
```

### Start the Flask API
```bash
python main.py --api
# → http://127.0.0.1:5000/
```

### Process a video file
```bash
python main.py --video testing.mp4
```

### Live webcam detection
```bash
python main.py --camera 0
# Press ESC to stop
```

### GUI (Haversine map tool)
```bash
python main.py --gui
```

### Self-test
```bash
python main.py --test
# Runs: import check, IoU calc, Haversine distance, model file, config file
```

---

## 🧪 Built-in Tests (`main.py --test`)

| # | Test | Pass condition |
|---|------|---------------|
| 1 | Module imports | All 3 core modules import without error |
| 2 | IoU calculation | `calculate_iou([0,0,100,100], [50,50,150,150])` ≈ 0.143 |
| 3 | Haversine distance | Chennai → Bangalore = 280–300 km |
| 4 | YOLO model file | `models/yolov8n.pt` exists (auto-downloads if missing) |
| 5 | Config file | `config.py` present |

---

## 📦 Key Dependencies

```
ultralytics     # YOLOv8 model
opencv-python   # Video capture, frame processing, bounding boxes
flask           # REST API server
numpy           # IoU, speed calculations
psutil          # RAM-based model selection
requests        # Overpass API + OpenWeatherMap calls
```

Full list in `Requirements.txt`.

---

## 👥 Team

| Name | Roll |
|------|------|
| Abhirami Ramadas | 02 |
| Aiswarya Rajeev Nair | 04 |
| Anola Saju | 11 |
| Gopika S S | 18 |

**Guided by:** Prof. Seena Thomas &nbsp;|&nbsp; **Coordinator:** Dr. Dileep V K  
Amrita Vishwa Vidyapeetham
