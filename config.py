# ==========================================================
# ⚙️ AI See You - Complete Configuration File
# ==========================================================
# ⚠️  SECURITY: Never commit real passwords/API keys to Git!
#     Use environment variables in production.
# ==========================================================

import os

# ----------------------------------------------------------
# 📧 Email Alert Settings
# ----------------------------------------------------------
SENDER_EMAIL    = os.getenv("SENDER_EMAIL",    "aiseeyou.alerts@gmail.com")
EMAIL_PASSWORD  = os.getenv("EMAIL_PASSWORD",  "zefyjcoykbphxuzd")   # Use Gmail App Password

# Who gets the emergency alert (hospitals, ambulances, etc.)
EMERGENCY_CONTACTS = [
    os.getenv("EMERGENCY_EMAIL_1", "anolasaju04@gmail.com"),
    # Add more recipients here
]

# Family / insurance contacts for HIGH/CRITICAL accidents
NOMINEE_CONTACTS = [
    os.getenv("NOMINEE_EMAIL_1", "abhiramiramadas2004@gmail.com"),
]

# Set True only after filling real email credentials above
ENABLE_EMAIL_ALERTS = True


# ----------------------------------------------------------
# 🗺️ Location Defaults (Chennai, India)
# ----------------------------------------------------------
DEFAULT_LATITUDE  = float(os.getenv("DEFAULT_LAT", "9.9312"))
DEFAULT_LONGITUDE = float(os.getenv("DEFAULT_LON", "76.2673"))

# Accident location alias (used in some alert templates)
ACCIDENT_LOCATION = (DEFAULT_LATITUDE, DEFAULT_LONGITUDE)


# ----------------------------------------------------------
# 🌦️ Weather API (OpenWeatherMap)
# ----------------------------------------------------------
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")   # Free tier at openweathermap.org


# ----------------------------------------------------------
# 🧠 YOLO Model Paths
# ----------------------------------------------------------
MODEL_PATHS = {
    "light":  "models/yolov8n.pt",   # < 4 GB RAM
    "medium": "models/yolov8s.pt",   # 4–8 GB RAM
    "heavy":  "models/yolov8m.pt",   # > 8 GB RAM
}


# ----------------------------------------------------------
# 🚗 Detection Thresholds
# ----------------------------------------------------------
# IoU thresholds for severity classification
IOU_THRESHOLD_LOW    = 0.30   # Minimum IoU to flag a collision
IOU_THRESHOLD_MEDIUM = 0.45
IOU_THRESHOLD_HIGH   = 0.60

# Speed thresholds (pixels per frame → maps to severity)
SPEED_LOW    = 15
SPEED_MEDIUM = 30
SPEED_HIGH   = 50

# Minimum speed to avoid flagging parked vehicles
MIN_SPEED_FOR_ACCIDENT = 5    # px/frame


# ----------------------------------------------------------
# 🌐 Flask Server Settings
# ----------------------------------------------------------
FLASK_HOST  = "0.0.0.0"
FLASK_PORT  = 5000
DEBUG_MODE  = False            # Set True only during development


# ----------------------------------------------------------
# 📁 File Paths
# ----------------------------------------------------------
UPLOAD_FOLDER = "uploads"


# ----------------------------------------------------------
# 🔠 OCR / Number Plate Recognition
# ----------------------------------------------------------
ENABLE_OCR = False             # Requires: pip install easyocr