 # ==========================================================
# � AI Accident Detection System - GUI Application
# ==========================================================

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import math
import threading
import time
import os
import requests
from datetime import datetime

# OpenCV for video processing
try:
    import cv2
    from PIL import Image, ImageTk
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("⚠️ OpenCV/PIL not available - video features disabled")

# Import detection system
try:
    from detection import AccidentDetector, VEHICLE_CLASSES
    DETECTION_AVAILABLE = True
except ImportError:
    DETECTION_AVAILABLE = False
    print("⚠️ Detection module not available")

# Import OSM functions
try:
    from OSM import haversine_distance, get_emergency_info
except ImportError:
    def haversine_distance(lat1, lon1, lat2, lon2):
        R = 6371
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
    
    def get_emergency_info(lat, lon):
        return None

# Import config
try:
    from config import DEFAULT_LATITUDE, DEFAULT_LONGITUDE
except ImportError:
    DEFAULT_LATITUDE = 9.9312
    DEFAULT_LONGITUDE = 76.2673


def get_current_location():
    """Detect device location via IP geolocation."""
    try:
        r = requests.get("http://ip-api.com/json/", timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d.get("status") == "success":
                return d["lat"], d["lon"], d.get("city", "Unknown")
    except Exception as e:
        print(f"ip-api error: {e}")
    try:
        r = requests.get("https://ipinfo.io/json", timeout=5)
        if r.status_code == 200:
            d = r.json()
            loc = d.get("loc", "").split(",")
            if len(loc) == 2:
                return float(loc[0]), float(loc[1]), d.get("city", "Unknown")
    except Exception as e:
        print(f"ipinfo error: {e}")
    return None, None, None


class AccidentDetectionGUI:
    """Full-featured GUI for Accident Detection System"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("🚗 AI Accident Detection System")
        self.root.geometry("1200x800")
        self.root.resizable(True, True)
        
        # Detection state
        self.detector = None
        self.is_detecting = False
        self.video_source = None
        self.cap = None
        self.current_frame = None
        self.accidents_log = []

        # Popup control so alerts don't spam
        self.last_popup_time = 0
        self.popup_cooldown = 10  # seconds between alert popups
        self.popup_open = False
        
        # Location
        self.latitude = DEFAULT_LATITUDE
        self.longitude = DEFAULT_LONGITUDE
        
        # Configure styles
        self.style = ttk.Style()
        self.style.configure('Title.TLabel', font=('Helvetica', 18, 'bold'))
        self.style.configure('Header.TLabel', font=('Helvetica', 12, 'bold'))
        self.style.configure('Status.TLabel', font=('Helvetica', 10))
        self.style.configure('Alert.TLabel', font=('Helvetica', 11, 'bold'), foreground='red')
        self.style.configure('Safe.TLabel', font=('Helvetica', 11, 'bold'), foreground='green')
        
        # Create GUI
        self.create_widgets()
        
        # Initialize detector
        self.init_detector()
    
    def init_detector(self):
        """Initialize the accident detector"""
        if DETECTION_AVAILABLE:
            try:
                self.detector = AccidentDetector()
                self.log_message("✅ AI Model loaded successfully")
            except Exception as e:
                self.log_message(f"❌ Failed to load AI model: {e}")
        else:
            self.log_message("⚠️ Detection module not available")
    
    def create_widgets(self):
        """Create all GUI widgets"""
        
        # Main container with PanedWindow for resizable sections
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # ===== LEFT PANEL - Video & Detection =====
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=3)
        
        # Title
        title_label = ttk.Label(
            left_frame, 
            text="🚗 AI Accident Detection System",
            style='Title.TLabel'
        )
        title_label.pack(pady=(0, 10))
        
        # Video Display Frame
        video_container = ttk.LabelFrame(left_frame, text="📹 Live Detection Feed", padding="5")
        video_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.video_label = ttk.Label(video_container, text="No video source selected")
        self.video_label.pack(fill=tk.BOTH, expand=True)
        
        # Detection Status
        self.detection_status = ttk.Label(
            left_frame,
            text="🟢 Status: Ready",
            style='Safe.TLabel'
        )
        self.detection_status.pack(pady=5)
        
        # Control Buttons
        control_frame = ttk.Frame(left_frame)
        control_frame.pack(fill=tk.X, pady=10)
        
        self.webcam_btn = ttk.Button(
            control_frame,
            text="📷 Start Webcam",
            command=self.start_webcam
        )
        self.webcam_btn.pack(side=tk.LEFT, padx=5)
        
        self.video_btn = ttk.Button(
            control_frame,
            text="🎬 Open Video File",
            command=self.open_video_file
        )
        self.video_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(
            control_frame,
            text="⏹️ Stop Detection",
            command=self.stop_detection,
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.screenshot_btn = ttk.Button(
            control_frame,
            text="📸 Screenshot",
            command=self.take_screenshot,
            state=tk.DISABLED
        )
        self.screenshot_btn.pack(side=tk.LEFT, padx=5)
        
        # Stats Frame
        stats_frame = ttk.LabelFrame(left_frame, text="📊 Detection Statistics", padding="10")
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.stats_labels = {}
        stats = [
            ("frames", "Frames Processed:", "0"),
            ("vehicles", "Vehicles Detected:", "0"),
            ("accidents", "Accidents Detected:", "0"),
            ("fps", "FPS:", "0"),
        ]
        
        for i, (key, label, default) in enumerate(stats):
            ttk.Label(stats_frame, text=label).grid(row=0, column=i*2, sticky="e", padx=5)
            self.stats_labels[key] = ttk.Label(stats_frame, text=default, font=('Consolas', 10, 'bold'))
            self.stats_labels[key].grid(row=0, column=i*2+1, sticky="w", padx=5)
        
        # ===== RIGHT PANEL - Controls & Logs =====
        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=2)
        
        # Notebook for tabs
        notebook = ttk.Notebook(right_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # ----- Tab 1: Location & Emergency -----
        location_tab = ttk.Frame(notebook, padding="10")
        notebook.add(location_tab, text="📍 Location & Emergency")
        
        # Location Settings
        loc_frame = ttk.LabelFrame(location_tab, text="📍 Current Location", padding="10")
        loc_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(loc_frame, text="Latitude:").grid(row=0, column=0, sticky="w", padx=5)
        self.lat_entry = ttk.Entry(loc_frame, width=15)
        self.lat_entry.grid(row=0, column=1, padx=5)
        self.lat_entry.insert(0, str(self.latitude))
        
        ttk.Label(loc_frame, text="Longitude:").grid(row=0, column=2, sticky="w", padx=5)
        self.lon_entry = ttk.Entry(loc_frame, width=15)
        self.lon_entry.grid(row=0, column=3, padx=5)
        self.lon_entry.insert(0, str(self.longitude))
        
        ttk.Button(
            loc_frame,
            text="📍 Update Location",
            command=self.update_location
        ).grid(row=0, column=4, padx=10)
        
        # Preset Locations
        preset_frame = ttk.LabelFrame(location_tab, text="🌍 Quick Locations", padding="10")
        preset_frame.pack(fill=tk.X, pady=(0, 10))
        
        presets = [
            ("Trivandrum",  8.5241,  76.9366),
            ("Kochi",       9.9312,  76.2673),
            ("Kozhikode",  11.2588,  75.7804),
            ("Thrissur",   10.5276,  76.2144),
            ("Kollam",      8.8932,  76.6141),
        ]

        for i, (name, lat, lon) in enumerate(presets):
            ttk.Button(
                preset_frame,
                text=name,
                command=lambda la=lat, lo=lon, n=name: self.set_location(la, lo, n),
                width=12
            ).grid(row=0, column=i, padx=2, pady=2)

        # Auto-detect current device location
        ttk.Button(
            preset_frame,
            text="📍 My Location (Auto-Detect)",
            command=self.detect_my_location,
        ).grid(row=1, column=0, columnspan=3, padx=2, pady=(6, 0), sticky="w")
        
        # Emergency Services
        emergency_frame = ttk.LabelFrame(location_tab, text="🚨 Emergency Services", padding="10")
        emergency_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.emergency_text = tk.Text(
            emergency_frame,
            height=15,
            font=('Consolas', 9),
            wrap=tk.WORD
        )
        self.emergency_text.pack(fill=tk.BOTH, expand=True)
        
        ttk.Button(
            location_tab,
            text="🔍 Find Nearby Emergency Services",
            command=self.find_emergency_services
        ).pack(pady=5)
        
        # ----- Tab 2: Distance Calculator -----
        distance_tab = ttk.Frame(notebook, padding="10")
        notebook.add(distance_tab, text="📏 Distance Calculator")
        
        # Point 1
        p1_frame = ttk.LabelFrame(distance_tab, text="📍 Point 1", padding="10")
        p1_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(p1_frame, text="Lat:").grid(row=0, column=0)
        self.dist_lat1 = ttk.Entry(p1_frame, width=12)
        self.dist_lat1.grid(row=0, column=1, padx=5)
        self.dist_lat1.insert(0, "13.0827")
        
        ttk.Label(p1_frame, text="Lon:").grid(row=0, column=2)
        self.dist_lon1 = ttk.Entry(p1_frame, width=12)
        self.dist_lon1.grid(row=0, column=3, padx=5)
        self.dist_lon1.insert(0, "80.2707")
        
        # Point 2
        p2_frame = ttk.LabelFrame(distance_tab, text="📍 Point 2", padding="10")
        p2_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(p2_frame, text="Lat:").grid(row=0, column=0)
        self.dist_lat2 = ttk.Entry(p2_frame, width=12)
        self.dist_lat2.grid(row=0, column=1, padx=5)
        self.dist_lat2.insert(0, "12.9716")
        
        ttk.Label(p2_frame, text="Lon:").grid(row=0, column=2)
        self.dist_lon2 = ttk.Entry(p2_frame, width=12)
        self.dist_lon2.grid(row=0, column=3, padx=5)
        self.dist_lon2.insert(0, "77.5946")
        
        ttk.Button(
            distance_tab,
            text="📏 Calculate Distance",
            command=self.calculate_distance
        ).pack(pady=10)
        
        self.distance_result = tk.Text(
            distance_tab,
            height=12,
            font=('Consolas', 9),
            wrap=tk.WORD
        )
        self.distance_result.pack(fill=tk.BOTH, expand=True)
        
        # ----- Tab 3: Accident Log -----
        log_tab = ttk.Frame(notebook, padding="10")
        notebook.add(log_tab, text="📋 Detection Log")
        
        self.log_text = tk.Text(
            log_tab,
            height=20,
            font=('Consolas', 9),
            wrap=tk.WORD
        )
        # Use a proper sibling scrollbar instead of packing it inside the Text widget
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        log_scrollbar = ttk.Scrollbar(log_tab, orient="vertical", command=self.log_text.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        btn_frame = ttk.Frame(log_tab)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="🗑️ Clear Log", command=self.clear_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="💾 Save Log", command=self.save_log).pack(side=tk.LEFT, padx=5)
        
        # ----- Tab 4: Settings -----
        settings_tab = ttk.Frame(notebook, padding="10")
        notebook.add(settings_tab, text="⚙️ Settings")
        
        # Detection Settings
        det_settings = ttk.LabelFrame(settings_tab, text="🎯 Detection Settings", padding="10")
        det_settings.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(det_settings, text="Confidence Threshold:").grid(row=0, column=0, sticky="w")
        self.conf_scale = ttk.Scale(det_settings, from_=0.1, to=0.9, orient=tk.HORIZONTAL, length=200)
        self.conf_scale.set(0.3)
        self.conf_scale.grid(row=0, column=1, padx=10)
        
        ttk.Label(det_settings, text="Alert on Detection:").grid(row=1, column=0, sticky="w", pady=5)
        self.alert_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(det_settings, variable=self.alert_var).grid(row=1, column=1, sticky="w")
        
        ttk.Label(det_settings, text="Auto Screenshot:").grid(row=2, column=0, sticky="w", pady=5)
        self.auto_screenshot_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(det_settings, variable=self.auto_screenshot_var).grid(row=2, column=1, sticky="w")
        
        # Model Info
        model_frame = ttk.LabelFrame(settings_tab, text="🧠 AI Model Info", padding="10")
        model_frame.pack(fill=tk.X, pady=(0, 10))
        
        model_info = "YOLOv8 Nano (yolov8n.pt)" if DETECTION_AVAILABLE else "Detection not available"
        ttk.Label(model_frame, text=f"Model: {model_info}").pack(anchor="w")
        ttk.Label(model_frame, text="Detected Classes: Car, Motorcycle, Bus, Truck, Bicycle").pack(anchor="w")
        
        # Status bar at the bottom
        self.status_var = tk.StringVar(value="Ready - Select a video source to begin")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", padding=5)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Initial log message
        self.log_message("🚗 Accident Detection System initialized")
        self.log_message(f"📍 Default location: Chennai ({self.latitude}, {self.longitude})")
    
    def log_message(self, message):
        """Add a message to the log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
    
    def clear_log(self):
        """Clear the log"""
        self.log_text.delete(1.0, tk.END)
        self.log_message("Log cleared")
    
    def save_log(self):
        """Save log to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            with open(filename, 'w') as f:
                f.write(self.log_text.get(1.0, tk.END))
            self.log_message(f"Log saved to {filename}")
    
    def set_location(self, lat, lon, name=None):
        """Set location from preset"""
        # Update main location entries
        self.lat_entry.delete(0, tk.END)
        self.lat_entry.insert(0, str(lat))
        self.lon_entry.delete(0, tk.END)
        self.lon_entry.insert(0, str(lon))
        
        # Also update distance calculator "Point 1" so it stays in sync
        if hasattr(self, "dist_lat1") and hasattr(self, "dist_lon1"):
            self.dist_lat1.delete(0, tk.END)
            self.dist_lat1.insert(0, str(lat))
            self.dist_lon1.delete(0, tk.END)
            self.dist_lon1.insert(0, str(lon))

        # Propagate to detector / internal state
        self.update_location()
        if name:
            self.log_message(f"📍 Location set to {name}")
    
    def detect_my_location(self):
        """Auto-detect device location via IP and fill the lat/lon fields."""
        self.status_var.set("Detecting your location, please wait...")
        self.root.update()

        def _run():
            lat, lon, city = get_current_location()
            if lat is not None:
                self.root.after(0, lambda: self.set_location(lat, lon, f"My Location ({city})"))
                self.root.after(0, lambda: messagebox.showinfo(
                    "Location Detected",
                    f"City: {city}\nCoordinates: ({lat:.4f}, {lon:.4f})\n\n"
                    "Note: IP-based location is accurate to ~1-5 km."
                ))
            else:
                self.root.after(0, lambda: messagebox.showerror(
                    "Location Error",
                    "Could not detect location.\nPlease select a city or enter coordinates manually."
                ))
        threading.Thread(target=_run, daemon=True).start()

    def update_location(self):
        """Update current location from entry fields"""
        try:
            self.latitude = float(self.lat_entry.get())
            self.longitude = float(self.lon_entry.get())
            if self.detector:
                self.detector.set_location(self.latitude, self.longitude)
            self.status_var.set(f"📍 Location updated: ({self.latitude}, {self.longitude})")
        except ValueError:
            messagebox.showerror("Error", "Invalid coordinates")
    
    def start_webcam(self):
        """Start webcam detection"""
        if not CV2_AVAILABLE:
            messagebox.showerror("Error", "OpenCV not available. Install with: pip install opencv-python pillow")
            return
        
        if not DETECTION_AVAILABLE:
            messagebox.showerror("Error", "Detection module not available")
            return
        
        self.video_source = 0
        self.start_detection()
    
    def open_video_file(self):
        """Open video file for detection"""
        if not CV2_AVAILABLE:
            messagebox.showerror("Error", "OpenCV not available")
            return
        
        filename = filedialog.askopenfilename(
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv"),
                ("All files", "*.*")
            ]
        )
        if filename:
            self.video_source = filename
            self.start_detection()
    
    def start_detection(self):
        """Start the detection loop"""
        if self.is_detecting:
            return
        
        self.cap = cv2.VideoCapture(self.video_source)
        if not self.cap.isOpened():
            messagebox.showerror("Error", "Could not open video source")
            return
        
        self.is_detecting = True
        self.webcam_btn.config(state=tk.DISABLED)
        self.video_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.screenshot_btn.config(state=tk.NORMAL)
        
        source_name = "Webcam" if self.video_source == 0 else os.path.basename(str(self.video_source))
        self.log_message(f"▶️ Started detection on: {source_name}")
        self.status_var.set(f"🔴 Detecting... Source: {source_name}")
        
        # Start detection thread
        self.detection_thread = threading.Thread(target=self.detection_loop, daemon=True)
        self.detection_thread.start()
    
    def stop_detection(self):
        """Stop the detection loop"""
        self.is_detecting = False
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.webcam_btn.config(state=tk.NORMAL)
        self.video_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.screenshot_btn.config(state=tk.DISABLED)
        
        self.video_label.config(image='', text="No video source selected")
        self.detection_status.config(text="🟢 Status: Stopped", style='Safe.TLabel')
        self.log_message("⏹️ Detection stopped")
        self.status_var.set("Ready - Select a video source to begin")
    
    def detection_loop(self):
        """Main detection loop running in separate thread"""
        frame_count = 0
        start_time = time.time()
        accidents_count = 0
        
        while self.is_detecting and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                # Loop video or stop
                if self.video_source != 0:  # Video file
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    break
            
            frame_count += 1
            
            # Process frame with detector
            if self.detector:
                try:
                    processed_frame, accident_data = self.detector.process_frame(frame)
                    
                    # Handle accident detection
                    if accident_data:
                        accidents_count += 1
                        self.handle_accident(accident_data, processed_frame)
                    
                    frame = processed_frame
                except Exception as e:
                    self.log_message(f"⚠️ Detection error: {e}")
            
            # Store current frame for screenshot
            self.current_frame = frame.copy()
            
            # Update GUI (resize for display)
            display_frame = cv2.resize(frame, (640, 480))
            display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            
            # Convert to PhotoImage
            img = Image.fromarray(display_frame)
            imgtk = ImageTk.PhotoImage(image=img)
            
            # Update label in main thread
            self.root.after(0, self.update_video_display, imgtk, frame_count, accidents_count, start_time)
            
            # Small delay to prevent UI freeze
            time.sleep(0.01)
        
        # Detection ended
        self.root.after(0, self.stop_detection)
    
    def update_video_display(self, imgtk, frame_count, accidents_count, start_time):
        """Update video display in main thread"""
        if not self.is_detecting:
            return
        
        self.video_label.imgtk = imgtk
        self.video_label.config(image=imgtk, text='')
        
        # Update stats
        elapsed = time.time() - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0
        
        self.stats_labels['frames'].config(text=str(frame_count))
        self.stats_labels['accidents'].config(text=str(accidents_count))
        self.stats_labels['fps'].config(text=f"{fps:.1f}")
        
        if self.detector:
            vehicles = len(self.detector.tracker.tracks)
            self.stats_labels['vehicles'].config(text=str(vehicles))
    
    def handle_accident(self, accident_data, frame):
        """Handle detected accident — GUI display + email alert"""
        severity = accident_data.get('severity', 'UNKNOWN')
        impact   = accident_data.get('impact_score', 0)
        vehicles = accident_data.get('vehicle_types', [])

        # Always use latest GUI coordinates
        accident_data['latitude']  = self.latitude
        accident_data['longitude'] = self.longitude

        # Send email via detector.handle_accident() in background thread
        if self.detector:
            try:
                threading.Thread(
                    target=self.detector.handle_accident,
                    args=(accident_data, frame),
                    daemon=True
                ).start()
                self.root.after(0, lambda: self.log_message("📧 Email alert dispatched..."))
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"⚠️ Email error: {e}"))

        # Update GUI status
        self.root.after(0, lambda: self.detection_status.config(
            text=f"🔴 ACCIDENT DETECTED! Severity: {severity}",
            style='Alert.TLabel'
        ))

        # Log
        log_msg = f"🚨 ACCIDENT - Severity: {severity}, Impact: {impact:.1f}, Vehicles: {', '.join(vehicles)}"
        self.root.after(0, lambda: self.log_message(log_msg))

        # Auto screenshot
        if self.auto_screenshot_var.get():
            self.root.after(0, lambda: self.save_accident_screenshot(frame, severity))

        # Popup alert
        if self.alert_var.get():
            now = time.time()
            if (now - self.last_popup_time) >= self.popup_cooldown and not self.popup_open:
                self.last_popup_time = now
                self.root.after(0, lambda: self.show_accident_alert(severity, impact, vehicles))

        # Reset status after 3 seconds
        self.root.after(3000, lambda: self.detection_status.config(
            text="🟢 Status: Monitoring...",
            style='Safe.TLabel'
        ))
    
    def show_accident_alert(self, severity, impact, vehicles):
        """Show accident alert popup"""
        self.popup_open = True
        msg = f"""
⚠️ ACCIDENT DETECTED!

Severity: {severity}
Impact Score: {impact:.1f}
Vehicles: {', '.join(vehicles)}
Location: ({self.latitude}, {self.longitude})
Time: {datetime.now().strftime('%H:%M:%S')}

Emergency services have been notified.
        """
        try:
            messagebox.showwarning("Accident Detected!", msg)
        finally:
            # Allow future popups after this one is closed
            self.popup_open = False
    
    def save_accident_screenshot(self, frame, severity):
        """Save screenshot of accident"""
        os.makedirs("uploads/accidents", exist_ok=True)
        filename = f"uploads/accidents/accident_{severity}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        cv2.imwrite(filename, frame)
        self.log_message(f"📸 Screenshot saved: {filename}")
    
    def take_screenshot(self):
        """Take manual screenshot"""
        if self.current_frame is not None:
            os.makedirs("uploads/screenshots", exist_ok=True)
            filename = f"uploads/screenshots/screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            cv2.imwrite(filename, self.current_frame)
            self.log_message(f"📸 Screenshot saved: {filename}")
            messagebox.showinfo("Screenshot", f"Saved to: {filename}")
    
    def find_emergency_services(self):
        """Find nearby emergency services"""
        # Always sync coords from entry fields first
        self.update_location()
        self.emergency_text.delete(1.0, tk.END)
        self.emergency_text.insert(tk.END, f"Searching near ({self.latitude:.4f}, {self.longitude:.4f})...\n")
        self.root.update()

        try:
            info = get_emergency_info(self.latitude, self.longitude)
            
            if info:
                result = f"""
╔══════════════════════════════════════════════╗
║        🚨 EMERGENCY SERVICES NEARBY          ║
╚══════════════════════════════════════════════╝

📍 Location: {info['location']['address'][:50]}...
   Coordinates: ({self.latitude}, {self.longitude})

═══════════════════════════════════════════════

🏥 NEAREST HOSPITAL:
"""
                if info.get('nearest_hospital'):
                    h = info['nearest_hospital']
                    result += f"""   Name: {h['name']}
   Distance: {h['distance_km']} km
   Phone: {h['phone']}
"""
                else:
                    result += "   No hospitals found nearby\n"
                
                result += "\n👮 NEAREST POLICE STATION:\n"
                if info.get('nearest_police'):
                    p = info['nearest_police']
                    result += f"""   Name: {p['name']}
   Distance: {p['distance_km']} km
   Phone: {p['phone']}
"""
                else:
                    result += "   No police stations found nearby\n"
                
                result += "\n🌤️ WEATHER CONDITIONS:\n"
                w = info.get('weather', {})
                result += f"""   Weather: {w.get('weather', 'N/A')}
   Temperature: {w.get('temperature', 'N/A')}°C
   Visibility: {w.get('visibility', 'N/A')} km
   Risk Factor: {w.get('risk_factor', 'N/A')}
"""
                
                result += "\n═══════════════════════════════════════════════\n"
                
                self.emergency_text.delete(1.0, tk.END)
                self.emergency_text.insert(tk.END, result)
            else:
                self.emergency_text.delete(1.0, tk.END)
                self.emergency_text.insert(tk.END, "❌ Could not fetch emergency services.\nCheck your internet connection.")
                
        except Exception as e:
            self.emergency_text.delete(1.0, tk.END)
            self.emergency_text.insert(tk.END, f"❌ Error: {e}")
    
    def calculate_distance(self):
        """Calculate distance between two points"""
        try:
            lat1 = float(self.dist_lat1.get())
            lon1 = float(self.dist_lon1.get())
            lat2 = float(self.dist_lat2.get())
            lon2 = float(self.dist_lon2.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid coordinates")
            return
        
        distance = haversine_distance(lat1, lon1, lat2, lon2)
        
        result = f"""
╔══════════════════════════════════════════════╗
║       📏 HAVERSINE DISTANCE CALCULATION      ║
╚══════════════════════════════════════════════╝

📍 Point 1: ({lat1}, {lon1})
📍 Point 2: ({lat2}, {lon2})

═══════════════════════════════════════════════

📏 DISTANCE: {distance:.2f} km ({distance * 0.621371:.2f} miles)

═══════════════════════════════════════════════

⏱️ Estimated Response Time:
   🚗 Car (60 km/h):        {distance/60*60:.1f} min
   🚑 Ambulance (80 km/h):  {distance/80*60:.1f} min
   🚁 Helicopter (200 km/h): {distance/200*60:.1f} min

═══════════════════════════════════════════════
"""
        
        self.distance_result.delete(1.0, tk.END)
        self.distance_result.insert(tk.END, result)


def main():
    """Launch the GUI application"""
    root = tk.Tk()
    
    # Set icon if available
    try:
        root.iconbitmap('icon.ico')
    except:
        pass
    
    app = AccidentDetectionGUI(root)
    
    # Handle window close
    def on_closing():
        if app.is_detecting:
            app.stop_detection()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()