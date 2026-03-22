 # ==========================================================
# 🧪 Full Alert Flow Test — bypasses detection, tests email
# Usage: python test_full_alert.py
# ==========================================================

import sys
import os

# ── Make sure imports work ────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 55)
print("🧪 AI See You — Full Alert Flow Test")
print("=" * 55)

# ── Step 1: Import config ─────────────────────────────────
print("\n[1] Loading config...")
try:
    from config import (
        SENDER_EMAIL, EMAIL_PASSWORD, EMERGENCY_CONTACTS,
        NOMINEE_CONTACTS, ENABLE_EMAIL_ALERTS
    )
    print(f"   ✅ SENDER_EMAIL       : {SENDER_EMAIL}")
    print(f"   ✅ ENABLE_EMAIL_ALERTS: {ENABLE_EMAIL_ALERTS}")
    print(f"   ✅ EMERGENCY_CONTACTS : {EMERGENCY_CONTACTS}")
    print(f"   ✅ NOMINEE_CONTACTS   : {NOMINEE_CONTACTS}")

    if not ENABLE_EMAIL_ALERTS:
        print()
        print("   ❌ ENABLE_EMAIL_ALERTS is False!")
        print("      → Open config.py and set ENABLE_EMAIL_ALERTS = True")
        sys.exit(1)

    if not EMERGENCY_CONTACTS or EMERGENCY_CONTACTS[0] == "hospital@example.com":
        print()
        print("   ❌ EMERGENCY_CONTACTS has placeholder email!")
        print("      → Add a real email address in config.py")
        sys.exit(1)

except ImportError as e:
    print(f"   ❌ config.py import failed: {e}")
    sys.exit(1)

# ── Step 2: Import alert system ───────────────────────────
print("\n[2] Loading alert system...")
try:
    from alert import AlertSystem
    alert = AlertSystem()
    print("   ✅ AlertSystem loaded")
    print(f"   ✅ Sender in AlertSystem: {alert.sender_email}")
except ImportError as e:
    print(f"   ❌ alert.py import failed: {e}")
    sys.exit(1)

# ── Step 3: Build dummy accident data with hospital details
print("\n[3] Building test accident data with hospital details...")
accident_data = {
    "severity":          "HIGH",
    "latitude":          9.9312,
    "longitude":         76.2673,
    "address":           "MG Road, Ernakulam, Kochi, Kerala 682035",
    "impact_score":      75.0,
    "vehicles_count":    2,
    "iou":               0.55,
    "vehicle_types":     ["Car", "Bus"],
    # ✅ Hospital details
    "nearest_hospital":  "Ernakulam General Hospital",
    "hospital_distance": 1.2,
    "hospital_phone":    "+91-484-2361234",
    "hospital_address":  "Hospital Road, Ernakulam, Kochi, Kerala",
    "all_hospitals": [
        {"name": "Ernakulam General Hospital",  "distance_km": 1.2, "phone": "+91-484-2361234"},
        {"name": "Lakeshore Hospital",           "distance_km": 2.8, "phone": "+91-484-2701032"},
        {"name": "Amrita Institute of Medical",  "distance_km": 4.1, "phone": "+91-484-2801234"},
    ],
    # ✅ Police details
    "nearest_police":    "Ernakulam South Police Station",
    "police_distance":   0.9,
    "police_phone":      "+91-484-2394730",
    # ✅ Weather
    "weather":           "Clear",
    "weather_risk":      "Low",
    "temperature":       31,
    "visibility":        10,
}
print("   ✅ Accident data ready")

# ── Step 4: Send emergency alert email ───────────────────
print(f"\n[4] Sending emergency alert to: {EMERGENCY_CONTACTS}...")
try:
    alert.send_accident_alert(accident_data)
    print("   ✅ send_accident_alert() completed")
except Exception as e:
    print(f"   ❌ send_accident_alert() failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ── Step 5: Send nominee alert ────────────────────────────
print(f"\n[5] Sending nominee alert to: {NOMINEE_CONTACTS}...")
try:
    alert.send_nominee_alert(accident_data)
    print("   ✅ send_nominee_alert() completed")
except Exception as e:
    print(f"   ❌ send_nominee_alert() failed: {e}")

# ── Done ─────────────────────────────────────────────────
print()
print("=" * 55)
print("✅ FULL ALERT FLOW TEST COMPLETE")
print(f"   Check inbox of: {EMERGENCY_CONTACTS[0]}")
print(f"   Check inbox of: {NOMINEE_CONTACTS[0]}")
print("   (Also check Spam folder)")
print("=" * 55)