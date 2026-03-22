# ==========================================================
# 🚨 Alert System - Email & SMS Notifications
# ==========================================================

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import json

try:
    from config import (
        SENDER_EMAIL, EMAIL_PASSWORD, EMERGENCY_CONTACTS,
        NOMINEE_CONTACTS, ENABLE_EMAIL_ALERTS
    )
except ImportError:
    print("⚠️ config.py not found. Using default settings.")
    SENDER_EMAIL = ""
    EMAIL_PASSWORD = ""
    EMERGENCY_CONTACTS = []
    NOMINEE_CONTACTS = []
    ENABLE_EMAIL_ALERTS = False


class AlertSystem:
    """Handles all emergency alert notifications"""

    def __init__(self):
        self.sender_email  = SENDER_EMAIL
        self.email_password = EMAIL_PASSWORD
        self.last_alert_time = None
        self.alert_cooldown  = 30  # seconds

    # ----------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------
    def _create_base_message(self, recipient, subject):
        msg = MIMEMultipart()
        msg['From']    = self.sender_email
        msg['To']      = recipient
        msg['Subject'] = subject
        return msg

    def _attach_image(self, msg, image_path):
        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                img = MIMEImage(f.read())
                img.add_header('Content-Disposition', 'attachment',
                               filename=os.path.basename(image_path))
                msg.attach(img)
        return msg

    def _attach_file(self, msg, file_path):
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', 'attachment',
                                filename=os.path.basename(file_path))
                msg.attach(part)
        return msg

    def _send_email(self, msg, recipient):
        if not ENABLE_EMAIL_ALERTS:
            print(f"📧 [SIMULATED] Email would be sent to: {recipient}")
            print(f"   Subject: {msg['Subject']}")
            return True
        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(self.sender_email, self.email_password)
            server.sendmail(self.sender_email, recipient, msg.as_string())
            server.quit()
            print(f"✅ Email sent to: {recipient}")
            return True
        except Exception as e:
            print(f"❌ Email failed to {recipient}: {e}")
            return False

    # ----------------------------------------------------------
    # Build hospital details block for email body
    # ----------------------------------------------------------
    def _hospital_block(self, accident_data: dict) -> str:
        """
        Build a clearly formatted hospital + police section
        from whatever data was fetched from OSM and stored in accident_data.
        """
        lines = []
        lines.append("🏥 NEAREST HOSPITAL:")

        h_name  = accident_data.get('nearest_hospital', 'N/A')
        h_dist  = accident_data.get('hospital_distance', 'N/A')
        h_phone = accident_data.get('hospital_phone', 'N/A')
        h_addr  = accident_data.get('hospital_address', 'N/A')

        lines.append(f"   Name     : {h_name}")
        lines.append(f"   Distance : {h_dist} km")
        if h_phone and h_phone != 'N/A':
            lines.append(f"   Phone    : {h_phone}")
        if h_addr and h_addr != 'N/A':
            lines.append(f"   Address  : {h_addr}")

        lines.append("")
        lines.append("👮 NEAREST POLICE STATION:")

        p_name  = accident_data.get('nearest_police', 'N/A')
        p_dist  = accident_data.get('police_distance', 'N/A')
        p_phone = accident_data.get('police_phone', 'N/A')

        lines.append(f"   Name     : {p_name}")
        lines.append(f"   Distance : {p_dist} km")
        if p_phone and p_phone != 'N/A':
            lines.append(f"   Phone    : {p_phone}")

        # Show all hospitals if available
        all_hospitals = accident_data.get('all_hospitals', [])
        if len(all_hospitals) > 1:
            lines.append("")
            lines.append("🏥 OTHER NEARBY HOSPITALS:")
            for i, h in enumerate(all_hospitals[1:], start=2):
                lines.append(f"   {i}. {h.get('name','N/A')} — {h.get('distance_km','N/A')} km")
                if h.get('phone') and h.get('phone') != 'N/A':
                    lines.append(f"      Phone: {h.get('phone')}")

        return "\n".join(lines)

    # ----------------------------------------------------------
    # Main emergency alert email
    # ----------------------------------------------------------
    def send_accident_alert(self, accident_data, image_path=None, video_path=None):
        """
        Send emergency accident alert email with full hospital details.
        """
        severity = accident_data.get('severity', 'UNKNOWN')
        subject  = f"🚨 ACCIDENT ALERT — {severity} SEVERITY | AI See You System"

        hospital_block = self._hospital_block(accident_data)

        # Google Maps link for the accident location
        lat = accident_data.get('latitude', '')
        lon = accident_data.get('longitude', '')
        maps_link = f"https://www.google.com/maps?q={lat},{lon}" if lat and lon else "N/A"

        body = f"""
═══════════════════════════════════════════════════════════
🚨  EMERGENCY ACCIDENT DETECTION ALERT  🚨
        AI See You — Automated Detection System
═══════════════════════════════════════════════════════════

📅 Date / Time  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 ACCIDENT LOCATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Latitude     : {lat}
   Longitude    : {lon}
   Address      : {accident_data.get('address', 'N/A')}
   Google Maps  : {maps_link}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  ACCIDENT DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Severity     : {severity}
   Impact Score : {accident_data.get('impact_score', 'N/A')}
   Vehicles     : {accident_data.get('vehicles_count', 'N/A')}
   Types        : {', '.join(accident_data.get('vehicle_types', ['Unknown']))}
   Collision IoU: {accident_data.get('iou', 0):.2%}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏥  EMERGENCY SERVICES — PLEASE DISPATCH IMMEDIATELY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{hospital_block}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌤️  WEATHER CONDITIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Weather      : {accident_data.get('weather', 'N/A')}
   Temperature  : {accident_data.get('temperature', 'N/A')} °C
   Visibility   : {accident_data.get('visibility', 'N/A')} km
   Risk Factor  : {accident_data.get('weather_risk', 'N/A')}

═══════════════════════════════════════════════════════════
⚡  IMMEDIATE ACTION REQUIRED — DISPATCH EMERGENCY SERVICES
═══════════════════════════════════════════════════════════
Emergency Helpline: 108 (Ambulance) | 100 (Police) | 101 (Fire)

This is an automated alert from the AI See You Accident Detection System.
"""

        for recipient in EMERGENCY_CONTACTS:
            msg = self._create_base_message(recipient, subject)
            msg.attach(MIMEText(body, 'plain'))
            if image_path:
                self._attach_image(msg, image_path)
            if video_path:
                self._attach_file(msg, video_path)
            self._send_email(msg, recipient)

    # ----------------------------------------------------------
    # Family / nominee alert
    # ----------------------------------------------------------
    def send_nominee_alert(self, accident_data, victim_info=None):
        subject = "🚨 URGENT: Family Member Involved in Accident — AI See You"

        lat = accident_data.get('latitude', '')
        lon = accident_data.get('longitude', '')
        maps_link = f"https://www.google.com/maps?q={lat},{lon}" if lat and lon else "N/A"

        body = f"""
═══════════════════════════════════════════════════════════
🚨  URGENT FAMILY NOTIFICATION  🚨
═══════════════════════════════════════════════════════════

Dear Family Member,

A vehicle has been involved in an accident detected by the
AI See You Accident Detection System.

📅 Date / Time  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📍 ACCIDENT LOCATION:
   Address      : {accident_data.get('address', 'N/A')}
   GPS          : {lat}, {lon}
   Google Maps  : {maps_link}

⚠️  SEVERITY: {accident_data.get('severity', 'UNKNOWN')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏥  NEAREST HOSPITAL — GO HERE IMMEDIATELY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Name         : {accident_data.get('nearest_hospital', 'N/A')}
   Distance     : {accident_data.get('hospital_distance', 'N/A')} km
   Phone        : {accident_data.get('hospital_phone', 'N/A')}
   Address      : {accident_data.get('hospital_address', 'N/A')}

👮  NEAREST POLICE STATION:
   Name         : {accident_data.get('nearest_police', 'N/A')}
   Distance     : {accident_data.get('police_distance', 'N/A')} km
   Phone        : {accident_data.get('police_phone', 'N/A')}

═══════════════════════════════════════════════════════════
Emergency Helpline: 108 (Ambulance) | 100 (Police) | 112 (Emergency)
═══════════════════════════════════════════════════════════

AI See You — Automated Accident Detection System
"""
        for recipient in NOMINEE_CONTACTS:
            msg = self._create_base_message(recipient, subject)
            msg.attach(MIMEText(body, 'plain'))
            self._send_email(msg, recipient)

    # ----------------------------------------------------------
    # Blood donation request
    # ----------------------------------------------------------
    def send_blood_donation_request(self, accident_data, blood_type="Unknown"):
        subject = "🩸 URGENT: Blood Donation Required — Accident Nearby"

        body = f"""
═══════════════════════════════════════════════════════════
🩸  URGENT BLOOD DONATION REQUEST  🩸
═══════════════════════════════════════════════════════════

A severe accident has occurred. Immediate blood donation
is required to save a life.

📅 Date / Time  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🩸 BLOOD REQUIRED:
   Blood Type   : {blood_type}
   Urgency      : CRITICAL

🏥 PLEASE GO TO THIS HOSPITAL:
   Name         : {accident_data.get('nearest_hospital', 'N/A')}
   Distance     : {accident_data.get('hospital_distance', 'N/A')} km
   Phone        : {accident_data.get('hospital_phone', 'N/A')}
   Address      : {accident_data.get('hospital_address', 'N/A')}

📍 ACCIDENT LOCATION:
   {accident_data.get('address', 'N/A')}

YOUR DONATION CAN SAVE A LIFE!
═══════════════════════════════════════════════════════════
AI See You — Automated Accident Detection System
"""
        for recipient in NOMINEE_CONTACTS:
            msg = self._create_base_message(recipient, subject)
            msg.attach(MIMEText(body, 'plain'))
            self._send_email(msg, recipient)

    # ----------------------------------------------------------
    # Insurance claim
    # ----------------------------------------------------------
    def send_insurance_claim(self, accident_data, damage_assessment):
        subject = f"📋 Auto Insurance Claim — ACC-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        claim_data = {
            "claim_reference": f"ACC-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "timestamp":       datetime.now().isoformat(),
            "severity":        accident_data.get('severity'),
            "location": {
                "latitude":  accident_data.get('latitude'),
                "longitude": accident_data.get('longitude'),
                "address":   accident_data.get('address'),
            },
            "vehicles":        accident_data.get('vehicle_types', []),
            "damage":          damage_assessment,
            "nearest_hospital": accident_data.get('nearest_hospital'),
            "weather":         accident_data.get('weather'),
        }

        body = f"""
═══════════════════════════════════════════════════════════
📋  AUTOMATED INSURANCE CLAIM SUBMISSION
═══════════════════════════════════════════════════════════

Claim Reference : {claim_data['claim_reference']}
Submitted At    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

ACCIDENT SUMMARY:
   Severity     : {accident_data.get('severity', 'N/A')}
   Location     : {accident_data.get('address', 'N/A')}
   Vehicles     : {', '.join(accident_data.get('vehicle_types', []))}
   Impact Score : {accident_data.get('impact_score', 'N/A')}

DAMAGE ASSESSMENT:
   Level        : {damage_assessment.get('level', 'N/A')}
   Est. Cost    : ${damage_assessment.get('estimated_cost', 'N/A'):,}
   Repair Days  : {damage_assessment.get('repair_days', 'N/A')}
   Total Loss   : {'Yes' if damage_assessment.get('total_loss') else 'No'}

NEAREST HOSPITAL:
   {accident_data.get('nearest_hospital', 'N/A')} — {accident_data.get('hospital_distance', 'N/A')} km

Full claim data (JSON):
{json.dumps(claim_data, indent=2)}

═══════════════════════════════════════════════════════════
AI See You — Automated Accident Detection System
"""
        print(f"📋 Insurance claim generated: {claim_data['claim_reference']}")
        return claim_data


# ==========================================================
# Module-level singleton + convenience functions
# ==========================================================
alert_system = AlertSystem()


def send_emergency_alert(accident_data, image_path=None, video_path=None):
    """Send emergency alert with full hospital details."""
    alert_system.send_accident_alert(accident_data, image_path, video_path)


def send_family_notification(accident_data):
    """Notify family members."""
    alert_system.send_nominee_alert(accident_data)


# ==========================================================
# Self-test
# ==========================================================
if __name__ == "__main__":
    test_data = {
        "severity":          "HIGH",
        "latitude":          9.9312,
        "longitude":         76.2673,
        "address":           "MG Road, Ernakulam, Kochi, Kerala",
        "impact_score":      75.0,
        "vehicles_count":    2,
        "iou":               0.55,
        "vehicle_types":     ["Car", "Bus"],
        "weather":           "Clear",
        "temperature":       31,
        "visibility":        10,
        "weather_risk":      "Low",
        # Hospital details from OSM
        "nearest_hospital":  "Ernakulam General Hospital",
        "hospital_distance": 1.2,
        "hospital_phone":    "+91-484-2361234",
        "hospital_address":  "Hospital Road, Ernakulam, Kochi",
        "all_hospitals": [
            {"name": "Ernakulam General Hospital",  "distance_km": 1.2, "phone": "+91-484-2361234"},
            {"name": "Lakeshore Hospital",           "distance_km": 2.8, "phone": "+91-484-2701032"},
            {"name": "Amrita Institute of Medical",  "distance_km": 4.1, "phone": "+91-484-2801234"},
        ],
        "nearest_police":    "Ernakulam South Police Station",
        "police_distance":   0.9,
        "police_phone":      "+91-484-2394730",
    }

    print("🧪 Testing Alert System...")
    print("\n--- Emergency Alert (simulated) ---")
    alert_system.send_accident_alert(test_data)
    print("\n✅ Test complete!")