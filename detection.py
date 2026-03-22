# ==========================================================
# 🚗 AI-Based Real-Time Accident Detection System
# ==========================================================
# Features:
# - YOLO-based collision detection
# - Speed & severity estimation
# - Weather integration
# - Emergency service locator
# - Automated alerts (email/SMS)
# - Flask API for video processing
# - Number plate recognition (OCR)
# - Insurance claim automation
# - Video clip saving (before & after accident)
# - Audio alerts (sound + text-to-speech)
# - PDF report generation
# - Web dashboard
# ==========================================================

import cv2
import numpy as np
from ultralytics import YOLO
import os
import sys
import time
import threading
import psutil
from datetime import datetime
from collections import defaultdict
from flask import Flask, request, jsonify, Response, render_template, send_from_directory
import logging

# Import custom modules
try:
    from alert import alert_system, send_emergency_alert
    from OSM import get_emergency_info, emergency_locator, weather_service
    from config import (
        MODEL_PATHS, UPLOAD_FOLDER, FLASK_HOST, FLASK_PORT, DEBUG_MODE,
        IOU_THRESHOLD_LOW, IOU_THRESHOLD_MEDIUM, IOU_THRESHOLD_HIGH,
        SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH, DEFAULT_LATITUDE, DEFAULT_LONGITUDE,
        ENABLE_OCR
    )
except ImportError as e:
    print(f"⚠️ Module import warning: {e}")
    print("Using default configurations...")
    MODEL_PATHS = {"light": "models/yolov8n.pt"}
    UPLOAD_FOLDER = "uploads"
    FLASK_HOST = "0.0.0.0"
    FLASK_PORT = 5000
    DEBUG_MODE = True
    IOU_THRESHOLD_LOW = 0.3
    IOU_THRESHOLD_MEDIUM = 0.4
    IOU_THRESHOLD_HIGH = 0.5
    SPEED_LOW = 15
    SPEED_MEDIUM = 30
    SPEED_HIGH = 50
    DEFAULT_LATITUDE = 9.9312
    DEFAULT_LONGITUDE = 76.2673
    ENABLE_OCR = False

# Import new features
try:
    from features.video_clip import clip_saver, save_accident_clip, add_frame_to_buffer
    VIDEO_CLIP_ENABLED = True
except ImportError:
    VIDEO_CLIP_ENABLED = False
    print("⚠️ Video clip feature not available")

try:
    from features.audio_alert import audio_alert, alert_accident, play_sound
    AUDIO_ALERT_ENABLED = True
except ImportError:
    AUDIO_ALERT_ENABLED = False
    print("⚠️ Audio alert feature not available")

try:
    from features.pdf_report import generate_accident_report
    PDF_REPORT_ENABLED = True
except ImportError:
    PDF_REPORT_ENABLED = False
    print("⚠️ PDF report feature not available")

try:
    from features.database import AccidentDatabase
    DATABASE_ENABLED = True
    accident_db = AccidentDatabase()
except ImportError:
    DATABASE_ENABLED = False
    accident_db = None
    print("⚠️ Database feature not available")

try:
    from features.excel_export import export_accidents_to_excel
    EXCEL_EXPORT_ENABLED = True
except ImportError:
    EXCEL_EXPORT_ENABLED = False
    print("⚠️ Excel export feature not available")

try:
    from features.map_generator import generate_accident_map
    MAP_ENABLED = True
except ImportError:
    MAP_ENABLED = False
    print("⚠️ Map generator feature not available")

# Configure logging (UTF-8 encoding for Windows)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs.txt', encoding='utf-8'),
        logging.StreamHandler(open(1, 'w', encoding='utf-8', closefd=False))
    ]
)
logger = logging.getLogger(__name__)

# ==========================================================
# Flask Application
# ==========================================================
app = Flask(__name__, template_folder='templates')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload

# ==========================================================
# Create necessary directories
# ==========================================================
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("models", exist_ok=True)


# ==========================================================
# Dynamic Model Selection based on System Memory
# ==========================================================
def select_model():
    """Select YOLO model based on available system memory"""
    available_memory = psutil.virtual_memory().available / (1024 ** 3)  # GB
    
    if available_memory >= 8:
        model_type = "heavy"
        model_name = "yolov8m.pt"
    elif available_memory >= 4:
        model_type = "medium"
        model_name = "yolov8s.pt"
    else:
        model_type = "light"
        model_name = "yolov8n.pt"
    
    model_path = MODEL_PATHS.get(model_type, "models/yolov8n.pt")
    
    # Check if model exists, fallback to yolov8n
    if not os.path.exists(model_path):
        model_path = "models/yolov8n.pt"
        model_name = "yolov8n.pt"
    
    logger.info(f"🧠 System Memory: {available_memory:.1f}GB | Model: {model_name}")
    return model_path


# ==========================================================
# Vehicle Classes in COCO Dataset
# ==========================================================
VEHICLE_CLASSES = {
    2: "Car",
    3: "Motorcycle",
    5: "Bus",
    7: "Truck",
    1: "Bicycle"
}


# ==========================================================
# IoU Calculation
# ==========================================================
def calculate_iou(boxA, boxB):
    """
    Calculate Intersection over Union (IoU) between two bounding boxes
    
    Args:
        boxA, boxB: Bounding boxes [x1, y1, x2, y2]
        
    Returns:
        IoU value between 0 and 1
    """
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interWidth = max(0, xB - xA)
    interHeight = max(0, yB - yA)
    interArea = interWidth * interHeight

    areaA = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    areaB = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

    iou = interArea / (areaA + areaB - interArea + 1e-6)
    return iou


# ==========================================================
# Vehicle Tracker for Speed Estimation
# ==========================================================
class VehicleTracker:
    """Tracks vehicles across frames for speed estimation"""
    
    def __init__(self):
        self.tracks = defaultdict(list)  # {track_id: [(frame_num, center, box), ...]}
        self.next_id = 0
        self.max_distance = 100  # Max pixel distance to match vehicles
        self.max_age = 30  # Max frames to keep track alive
        
    def update(self, boxes, frame_num):
        """
        Update tracks with new detections
        
        Args:
            boxes: List of [x1, y1, x2, y2, class_id]
            frame_num: Current frame number
            
        Returns:
            List of (track_id, box, speed) tuples
        """
        results = []
        used_tracks = set()
        
        for box in boxes:
            x1, y1, x2, y2 = box[:4]
            center = ((x1 + x2) / 2, (y1 + y2) / 2)
            class_id = box[4] if len(box) > 4 else 2
            
            # Find best matching track
            best_track = None
            best_distance = float('inf')
            
            for track_id, history in self.tracks.items():
                if track_id in used_tracks:
                    continue
                if not history:
                    continue
                    
                last_frame, last_center, _ = history[-1]
                if frame_num - last_frame > self.max_age:
                    continue
                    
                distance = np.sqrt((center[0] - last_center[0])**2 + 
                                   (center[1] - last_center[1])**2)
                
                if distance < best_distance and distance < self.max_distance:
                    best_distance = distance
                    best_track = track_id
            
            # Assign to existing track or create new one
            if best_track is not None:
                track_id = best_track
                used_tracks.add(track_id)
            else:
                track_id = self.next_id
                self.next_id += 1
            
            # Add to track history
            self.tracks[track_id].append((frame_num, center, box))
            
            # Keep only recent history
            if len(self.tracks[track_id]) > 30:
                self.tracks[track_id] = self.tracks[track_id][-30:]
            
            # Calculate speed (pixels per frame)
            speed = self._calculate_speed(track_id)
            
            results.append((track_id, box, speed, class_id))
        
        # Clean old tracks
        self._cleanup(frame_num)
        
        return results
    
    def _calculate_speed(self, track_id):
        """Calculate speed based on recent movement"""
        history = self.tracks.get(track_id, [])
        if len(history) < 2:
            return 0
        
        # Use last 5 frames for speed calculation
        recent = history[-5:]
        if len(recent) < 2:
            return 0
        
        total_distance = 0
        for i in range(1, len(recent)):
            prev_center = recent[i-1][1]
            curr_center = recent[i][1]
            distance = np.sqrt((curr_center[0] - prev_center[0])**2 + 
                               (curr_center[1] - prev_center[1])**2)
            total_distance += distance
        
        avg_speed = total_distance / (len(recent) - 1)
        return avg_speed
    
    def _cleanup(self, current_frame):
        """Remove old tracks"""
        tracks_to_remove = []
        for track_id, history in self.tracks.items():
            if history:
                last_frame = history[-1][0]
                if current_frame - last_frame > self.max_age:
                    tracks_to_remove.append(track_id)
        
        for track_id in tracks_to_remove:
            del self.tracks[track_id]


# ==========================================================
# Severity Calculator
# ==========================================================
class SeverityCalculator:
    """Calculates accident severity based on multiple factors"""
    
    @staticmethod
    def calculate(iou, speed1, speed2, vehicle_types):
        """
        Calculate accident severity
        
        Args:
            iou: Intersection over Union value
            speed1, speed2: Speeds of the two vehicles
            vehicle_types: Types of vehicles involved
            
        Returns:
            Tuple of (severity_level, impact_score, color)
        """
        # Base score from IoU (0-40 points)
        iou_score = min(iou * 80, 40)
        
        # Speed score (0-40 points)
        avg_speed = (speed1 + speed2) / 2
        if avg_speed > SPEED_HIGH:
            speed_score = 40
        elif avg_speed > SPEED_MEDIUM:
            speed_score = 25
        elif avg_speed > SPEED_LOW:
            speed_score = 15
        else:
            speed_score = 5
        
        # Vehicle type score (0-20 points)
        heavy_vehicles = ["Truck", "Bus"]
        type_score = 0
        for v_type in vehicle_types:
            if v_type in heavy_vehicles:
                type_score += 10
        type_score = min(type_score, 20)
        
        # Total impact score
        impact_score = iou_score + speed_score + type_score
        
        # Determine severity level
        if impact_score >= 70:
            severity = "CRITICAL"
            color = (0, 0, 255)  # Red
        elif impact_score >= 50:
            severity = "HIGH"
            color = (0, 69, 255)  # Orange-Red
        elif impact_score >= 35:
            severity = "MEDIUM"
            color = (0, 165, 255)  # Orange
        else:
            severity = "LOW"
            color = (0, 255, 255)  # Yellow
        
        return severity, impact_score, color


# ==========================================================
# Damage Estimator for Insurance Claims
# ==========================================================
class DamageEstimator:
    """Estimates vehicle damage for insurance processing"""
    
    @staticmethod
    def estimate(severity, vehicle_types, impact_score):
        """
        Estimate damage level and cost
        
        Args:
            severity: Accident severity level
            vehicle_types: Types of vehicles involved
            impact_score: Calculated impact score
            
        Returns:
            Dictionary with damage assessment
        """
        # Base cost estimation (in USD)
        base_costs = {
            "CRITICAL": 15000,
            "HIGH": 10000,
            "MEDIUM": 5000,
            "LOW": 2000
        }
        
        # Vehicle type multipliers
        type_multipliers = {
            "Car": 1.0,
            "Motorcycle": 0.5,
            "Bicycle": 0.2,
            "Bus": 2.5,
            "Truck": 2.0
        }
        
        base_cost = base_costs.get(severity, 5000)
        
        # Calculate average multiplier
        multiplier = 1.0
        if vehicle_types:
            multipliers = [type_multipliers.get(v, 1.0) for v in vehicle_types]
            multiplier = sum(multipliers) / len(multipliers)
        
        estimated_cost = int(base_cost * multiplier * (impact_score / 50))
        
        # Repair duration estimation (days)
        repair_days = {
            "CRITICAL": "30-45",
            "HIGH": "20-30",
            "MEDIUM": "10-20",
            "LOW": "5-10"
        }
        
        return {
            "level": severity,
            "estimated_cost": estimated_cost,
            "repair_days": repair_days.get(severity, "7-14"),
            "impact_score": impact_score,
            "vehicles": vehicle_types,
            "total_loss": severity == "CRITICAL" and impact_score > 85
        }


# ==========================================================
# Main Accident Detector Class
# ==========================================================
class AccidentDetector:
    """Main accident detection system"""
    
    def __init__(self, model_path=None):
        self.model_path = model_path or select_model()
        self.model = YOLO(self.model_path)
        self.tracker = VehicleTracker()
        self.frame_count = 0
        self.accidents_detected = []
        self.last_alert_time = 0
        self.alert_cooldown = 10  # seconds
        
        # Location (can be updated from GPS)
        self.latitude = DEFAULT_LATITUDE
        self.longitude = DEFAULT_LONGITUDE
        
        logger.info(f"Accident Detector initialized with {self.model_path}")
    
    def set_location(self, lat, lon):
        """Update current location"""
        self.latitude = lat
        self.longitude = lon
    
    def process_frame(self, frame, fps=30):
        """
        Process a single frame for accident detection
        
        Args:
            frame: OpenCV image (BGR)
            fps: Frames per second for video buffer
            
        Returns:
            Tuple of (annotated_frame, accident_data or None)
        """
        self.frame_count += 1
        
        # Add frame to video buffer for clip saving
        if VIDEO_CLIP_ENABLED:
            add_frame_to_buffer(frame, fps)
        
        # Run YOLO detection
        results = self.model(frame, verbose=False)
        
        # Extract vehicle detections
        boxes = []
        for r in results:
            for box in r.boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                
                # Lowered confidence from 0.5 to 0.3 for better detection
                if cls in VEHICLE_CLASSES and conf > 0.3:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    boxes.append([x1, y1, x2, y2, cls])
        
        # Update tracker
        tracked = self.tracker.update(boxes, self.frame_count)
        
        # Draw tracked vehicles
        for track_id, box, speed, class_id in tracked:
            x1, y1, x2, y2 = map(int, box[:4])
            vehicle_type = VEHICLE_CLASSES.get(class_id, "Vehicle")
            
            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Draw label
            label = f"{vehicle_type} #{track_id} | {speed:.1f}px/f"
            cv2.putText(frame, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Check for collisions
        accident_data = None
        for i in range(len(tracked)):
            for j in range(i + 1, len(tracked)):
                track1 = tracked[i]
                track2 = tracked[j]
                
                box1 = track1[1][:4]
                box2 = track2[1][:4]
                speed1 = track1[2]
                speed2 = track2[2]
                class1 = track1[3]
                class2 = track2[3]
                
                iou = calculate_iou(box1, box2)
                
                # Check if at least one vehicle is moving (avoid parked car false positives)
                min_speed = 5  # minimum pixels per frame
                try:
                    from config import MIN_SPEED_FOR_ACCIDENT
                    min_speed = MIN_SPEED_FOR_ACCIDENT
                except:
                    pass
                
                max_speed = max(speed1, speed2)
                
                # Only detect accident if: IoU threshold met AND at least one car is moving
                if iou > IOU_THRESHOLD_LOW and max_speed >= min_speed:
                    vehicle_types = [
                        VEHICLE_CLASSES.get(class1, "Vehicle"),
                        VEHICLE_CLASSES.get(class2, "Vehicle")
                    ]
                    
                    severity, impact_score, color = SeverityCalculator.calculate(
                        iou, speed1, speed2, vehicle_types
                    )
                    
                    # Draw collision indicator
                    cx = int((box1[0] + box1[2] + box2[0] + box2[2]) / 4)
                    cy = int((box1[1] + box1[3] + box2[1] + box2[3]) / 4)
                    
                    cv2.circle(frame, (cx, cy), 50, color, 3)
                    cv2.putText(frame, "!", (cx - 10, cy + 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.5, color, 3)
                    
                    # Draw accident info
                    cv2.putText(frame, f"ACCIDENT DETECTED",
                                (40, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)
                    cv2.putText(frame, f"Severity: {severity} ({impact_score:.0f})",
                                (40, 95), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                    cv2.putText(frame, f"IoU: {iou:.2%} | Vehicles: {', '.join(vehicle_types)}",
                                (40, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    
                    # Prepare accident data
                    accident_data = {
                        "timestamp": datetime.now().isoformat(),
                        "frame_number": self.frame_count,
                        "severity": severity,
                        "impact_score": impact_score,
                        "iou": iou,
                        "vehicles_count": 2,
                        "vehicle_types": vehicle_types,
                        "speeds": [speed1, speed2],
                        "latitude": self.latitude,
                        "longitude": self.longitude,
                        "collision_center": (cx, cy)
                    }
        
        # Draw frame info
        cv2.putText(frame, f"Frame: {self.frame_count}",
                    (frame.shape[1] - 150, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"Vehicles: {len(tracked)}",
                    (frame.shape[1] - 150, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return frame, accident_data
    
    def handle_accident(self, accident_data, frame):
        """
        Handle detected accident - save evidence and send alerts
        
        Args:
            accident_data: Accident information dictionary
            frame: Current frame with annotations
        """
        current_time = time.time()
        
        # Check cooldown
        if current_time - self.last_alert_time < self.alert_cooldown:
            return
        
        self.last_alert_time = current_time
        
        # Save accident frame
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = os.path.join(UPLOAD_FOLDER, f"accident_{timestamp}.jpg")
        cv2.imwrite(image_path, frame)
        logger.info(f"Accident frame saved: {image_path}")
        
        # Save video clip (if enabled)
        video_clip_path = None
        if VIDEO_CLIP_ENABLED:
            try:
                save_accident_clip(frame, accident_data)
                video_clip_path = f"uploads/clips/accident_clip_{accident_data['severity']}_{timestamp}.mp4"
                logger.info(f"Video clip recording triggered")
            except Exception as e:
                logger.warning(f"Could not save video clip: {e}")
        
        # Play audio alert (if enabled)
        if AUDIO_ALERT_ENABLED:
            try:
                alert_accident(accident_data)
                logger.info(f"Audio alert triggered for {accident_data['severity']} accident")
            except Exception as e:
                logger.warning(f"Could not play audio alert: {e}")
        
        # Get emergency services info
        try:
            emergency_info = get_emergency_info(
                accident_data['latitude'],
                accident_data['longitude']
            )
            
            h = emergency_info.get('nearest_hospital') or {}
            p = emergency_info.get('nearest_police') or {}
            accident_data.update({
                'address':           emergency_info['location']['address'],
                # Hospital details — included in email alert
                'nearest_hospital':  h.get('name', 'N/A'),
                'hospital_distance': h.get('distance_km', 'N/A'),
                'hospital_phone':    h.get('phone', 'N/A'),
                'hospital_address':  h.get('address', 'N/A'),
                'all_hospitals':     emergency_info.get('all_hospitals', []),
                # Police details
                'nearest_police':    p.get('name', 'N/A'),
                'police_distance':   p.get('distance_km', 'N/A'),
                'police_phone':      p.get('phone', 'N/A'),
                # Weather
                'weather':           emergency_info['weather']['weather'],
                'weather_risk':      emergency_info['weather']['risk_factor'],
                'temperature':       emergency_info['weather']['temperature'],
                'visibility':        emergency_info['weather']['visibility'],
            })
        except Exception as e:
            logger.warning(f"Could not fetch emergency info: {e}")
        
        # Estimate damage for insurance
        damage_assessment = DamageEstimator.estimate(
            accident_data['severity'],
            accident_data['vehicle_types'],
            accident_data['impact_score']
        )
        accident_data['damage_assessment'] = damage_assessment
        
        # Generate PDF report (if enabled)
        if PDF_REPORT_ENABLED:
            try:
                pdf_path = generate_accident_report(accident_data, image_path, video_clip_path)
                if pdf_path:
                    accident_data['pdf_report'] = pdf_path
                    logger.info(f"PDF report generated: {pdf_path}")
            except Exception as e:
                logger.warning(f"Could not generate PDF report: {e}")
        
        # Send alerts (in background thread)
        try:
            alert_thread = threading.Thread(
                target=self._send_alerts,
                args=(accident_data, image_path)
            )
            alert_thread.start()
        except Exception as e:
            logger.error(f"Alert thread error: {e}")
        
        # Store accident record
        self.accidents_detected.append(accident_data)
        logger.info(f"Accident #{len(self.accidents_detected)} recorded: {accident_data['severity']}")
        
        # Save to database (if enabled)
        if DATABASE_ENABLED and accident_db:
            try:
                accident_db.save_accident(accident_data)
                logger.info("✅ Accident saved to database")
            except Exception as e:
                logger.warning(f"Could not save to database: {e}")
    
    def _send_alerts(self, accident_data, image_path):
        """Send all alerts in background"""
        try:
            # Send emergency alert
            send_emergency_alert(accident_data, image_path)
            
            # Generate insurance claim
            claim = alert_system.send_insurance_claim(
                accident_data,
                accident_data.get('damage_assessment', {})
            )
            
            # If severity is HIGH or CRITICAL, notify family
            if accident_data['severity'] in ['HIGH', 'CRITICAL']:
                alert_system.send_nominee_alert(accident_data)
            
            # If CRITICAL, send blood donation request
            if accident_data['severity'] == 'CRITICAL':
                alert_system.send_blood_donation_request(accident_data)
            
            logger.info("✅ All alerts sent successfully")
        except Exception as e:
            logger.error(f"❌ Alert error: {e}")
    
    def process_video(self, video_path, display=True, save_output=False):
        """
        Process entire video for accident detection
        
        Args:
            video_path: Path to video file
            display: Whether to show live preview
            save_output: Whether to save annotated video
            
        Returns:
            List of detected accidents
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            logger.error(f"❌ Could not open video: {video_path}")
            return []
        
        # Video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        logger.info(f"Processing video: {video_path}")
        logger.info(f"   Resolution: {width}x{height} | FPS: {fps} | Frames: {total_frames}")
        
        # Video writer for output
        output_path = None
        writer = None
        if save_output:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(UPLOAD_FOLDER, f"output_{timestamp}.mp4")
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        self.frame_count = 0
        self.tracker = VehicleTracker()  # Reset tracker
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Process frame (pass fps for video clip buffer)
            annotated_frame, accident_data = self.process_frame(frame, fps)
            
            # Handle accident if detected
            if accident_data:
                self.handle_accident(accident_data, annotated_frame)
            
            # Save output frame
            if writer:
                writer.write(annotated_frame)
            
            # Display
            if display:
                cv2.imshow("AI Accident Detection System", annotated_frame)
                if cv2.waitKey(1) & 0xFF == 27:  # ESC to exit
                    break
        
        # Cleanup
        cap.release()
        if writer:
            writer.release()
        if display:
            cv2.destroyAllWindows()
        
        logger.info(f"Processing complete. Accidents detected: {len(self.accidents_detected)}")
        
        return self.accidents_detected


# ==========================================================
# Global detector instance
# ==========================================================
detector = None


def get_detector():
    """Get or create detector instance"""
    global detector
    if detector is None:
        detector = AccidentDetector()
    return detector


# ==========================================================
# Flask API Routes
# ==========================================================

@app.route('/')
def home():
    """API home page - redirects to dashboard"""
    return render_template('dashboard.html')


@app.route('/api')
def api_info():
    """API information endpoint"""
    return jsonify({
        "service": "AI Accident Detection System",
        "version": "2.0",
        "status": "running",
        "features": {
            "video_clip": VIDEO_CLIP_ENABLED,
            "audio_alert": AUDIO_ALERT_ENABLED,
            "pdf_report": PDF_REPORT_ENABLED
        },
        "endpoints": {
            "/": "GET - Web Dashboard",
            "/api": "GET - API Information",
            "/detect": "POST - Upload video for accident detection",
            "/health": "GET - Health check",
            "/accidents": "GET - List detected accidents",
            "/stream": "GET - Live camera stream",
            "/reports/<filename>": "GET - Download PDF reports",
            "/clips/<filename>": "GET - Download video clips"
        }
    })


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "model_loaded": detector is not None,
        "features": {
            "video_clip": VIDEO_CLIP_ENABLED,
            "audio_alert": AUDIO_ALERT_ENABLED,
            "pdf_report": PDF_REPORT_ENABLED
        },
        "timestamp": datetime.now().isoformat()
    })


@app.route('/reports/<filename>')
def download_report(filename):
    """Download PDF report"""
    return send_from_directory('uploads/reports', filename)


@app.route('/clips/<filename>')
def download_clip(filename):
    """Download video clip"""
    return send_from_directory('uploads/clips', filename)


@app.route('/detect', methods=['POST'])
def detect_accidents():
    """
    Detect accidents in uploaded video
    
    Accepts: video file upload
    Returns: JSON with detection results
    """
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided"}), 400
    
    video_file = request.files['video']
    
    if video_file.filename == '':
        return jsonify({"error": "No video selected"}), 400
    
    # Save uploaded video
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_path = os.path.join(UPLOAD_FOLDER, f"upload_{timestamp}.mp4")
    video_file.save(video_path)
    
    logger.info(f"📤 Video uploaded: {video_path}")
    
    # Process video
    det = get_detector()
    accidents = det.process_video(video_path, display=False, save_output=True)
    
    return jsonify({
        "success": True,
        "video_path": video_path,
        "accidents_detected": len(accidents),
        "accidents": accidents,
        "processing_time": datetime.now().isoformat()
    })


@app.route('/accidents')
def list_accidents():
    """List all detected accidents"""
    det = get_detector()
    return jsonify({
        "total_accidents": len(det.accidents_detected),
        "accidents": det.accidents_detected
    })


@app.route('/stream')
def video_stream():
    """Stream processed video (for web interface)"""
    def generate():
        cap = cv2.VideoCapture(0)  # Use webcam
        det = get_detector()
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            annotated_frame, _ = det.process_frame(frame)
            
            _, buffer = cv2.imencode('.jpg', annotated_frame)
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/export/excel')
def export_excel():
    """Export accidents to Excel file"""
    if not EXCEL_EXPORT_ENABLED:
        return jsonify({"error": "Excel export not available"}), 400
    
    det = get_detector()
    if not det.accidents_detected:
        return jsonify({"error": "No accidents to export"}), 400
    
    try:
        filepath = export_accidents_to_excel(det.accidents_detected)
        return send_from_directory(
            os.path.dirname(filepath),
            os.path.basename(filepath),
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Excel export error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/export/map')
def export_map():
    """Generate interactive accident map"""
    if not MAP_ENABLED:
        return jsonify({"error": "Map generator not available"}), 400
    
    det = get_detector()
    if not det.accidents_detected:
        return jsonify({"error": "No accidents to map"}), 400
    
    try:
        map_path = generate_accident_map(det.accidents_detected)
        return send_from_directory(
            os.path.dirname(map_path),
            os.path.basename(map_path),
            as_attachment=False,
            mimetype='text/html'
        )
    except Exception as e:
        logger.error(f"Map generation error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/statistics')
def get_statistics():
    """Get accident statistics"""
    if DATABASE_ENABLED and accident_db:
        return jsonify(accident_db.get_statistics())
    
    det = get_detector()
    accidents = det.accidents_detected
    
    stats = {
        "total": len(accidents),
        "by_severity": {
            "CRITICAL": len([a for a in accidents if a.get('severity') == 'CRITICAL']),
            "HIGH": len([a for a in accidents if a.get('severity') == 'HIGH']),
            "MEDIUM": len([a for a in accidents if a.get('severity') == 'MEDIUM']),
            "LOW": len([a for a in accidents if a.get('severity') == 'LOW'])
        }
    }
    return jsonify(stats)


# ==========================================================
# Main Entry Point
# ==========================================================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AI Accident Detection System")
    parser.add_argument('--video', type=str, help='Path to video file')
    parser.add_argument('--api', action='store_true', help='Run Flask API server')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--camera', type=int, default=0, help='Camera index for live detection')
    
    args = parser.parse_args()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║  🚗 AI-Based Real-Time Accident Detection System 🚨          ║
║  ─────────────────────────────────────────────────────────   ║
║  Version: 1.0                                                ║
║  Model: YOLO (Dynamic Selection)                             ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Initialize detector
    detector = AccidentDetector()
    
    if args.api or (not args.video and not args.camera):
        # Run Flask API server
        logger.info(f"🌐 Starting Flask API server on {FLASK_HOST}:{FLASK_PORT}")
        app.run(host=FLASK_HOST, port=FLASK_PORT, debug=args.debug or DEBUG_MODE)
    
    elif args.video:
        # Process video file
        if os.path.exists(args.video):
            detector.process_video(args.video, display=True, save_output=True)
        else:
            logger.error(f"❌ Video file not found: {args.video}")
    
    else:
        # Live camera detection
        cap = cv2.VideoCapture(args.camera)
        logger.info(f"📹 Starting live detection from camera {args.camera}")
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            annotated_frame, accident_data = detector.process_frame(frame)
            
            if accident_data:
                detector.handle_accident(accident_data, annotated_frame)
            
            cv2.imshow("AI Accident Detection - Live", annotated_frame)
            
            if cv2.waitKey(1) & 0xFF == 27:
                break
        
        cap.release()
        cv2.destroyAllWindows()