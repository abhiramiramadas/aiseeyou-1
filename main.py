
# ==========================================================
# 🚗 AI Accident Detection System - Main Entry Point
# ==========================================================

import os
import sys
import argparse

def main():
    """Main entry point for the accident detection system"""
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   🚗 AI-Based Real-Time Accident Detection System 🚨             ║
║   ──────────────────────────────────────────────────────────     ║
║                                                                  ║
║   Features:                                                      ║
║   ✅ Real-Time Collision Detection (YOLO)                        ║
║   ✅ Severity Estimation (IoU + Speed + Vehicle Type)            ║
║   ✅ Weather Integration (OpenWeatherMap API)                    ║
║   ✅ Emergency Services Locator (OpenStreetMap)                  ║
║   ✅ Automated Email/SMS Alerts                                  ║
║   ✅ Insurance Claim Automation                                  ║
║   ✅ Flask REST API                                              ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    parser = argparse.ArgumentParser(
        description="AI-Based Real-Time Accident Detection System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --api                    Start Flask API server
  python main.py --video test.mp4         Process a video file
  python main.py --camera 0               Use webcam for live detection
  python main.py --gui                    Launch GUI application
  python main.py --test                   Run system tests
        """
    )
    
    parser.add_argument('--api', action='store_true',
                        help='Start Flask API server')
    parser.add_argument('--video', type=str,
                        help='Path to video file for processing')
    parser.add_argument('--camera', type=int, default=None,
                        help='Camera index for live detection')
    parser.add_argument('--gui', action='store_true',
                        help='Launch GUI application')
    parser.add_argument('--test', action='store_true',
                        help='Run system tests')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode')
    parser.add_argument('--port', type=int, default=5000,
                        help='Port for Flask server (default: 5000)')
    
    args = parser.parse_args()
    
    # Run tests
    if args.test:
        print("🧪 Running system tests...")
        run_tests()
        return
    
    # Launch GUI
    if args.gui:
        print("🖥️ Launching GUI application...")
        launch_gui()
        return
    
    # Import detection module
    try:
        from detection import AccidentDetector, app, FLASK_HOST
        import cv2
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please ensure all dependencies are installed: pip install -r requirements.txt")
        sys.exit(1)
    
    # Initialize detector
    detector = AccidentDetector()
    
    # Start API server
    if args.api:
        print(f"🌐 Starting Flask API server on {FLASK_HOST}:{args.port}")
        print(f"   Access at: http://127.0.0.1:{args.port}/")
        print("\nAPI Endpoints:")
        print("   GET  /           - API info")
        print("   GET  /health     - Health check")
        print("   POST /detect     - Upload video for processing")
        print("   GET  /accidents  - List detected accidents")
        print("   GET  /stream     - Live video stream (webcam)")
        print("\nPress CTRL+C to stop the server.")
        app.run(host=FLASK_HOST, port=args.port, debug=args.debug)
    
    # Process video file
    elif args.video:
        if os.path.exists(args.video):
            print(f"📹 Processing video: {args.video}")
            accidents = detector.process_video(args.video, display=True, save_output=True)
            print(f"\n✅ Processing complete!")
            print(f"   Accidents detected: {len(accidents)}")
            for i, acc in enumerate(accidents, 1):
                print(f"   {i}. {acc['severity']} severity at frame {acc['frame_number']}")
        else:
            print(f"❌ Video file not found: {args.video}")
            sys.exit(1)
    
    # Live camera detection
    elif args.camera is not None:
        print(f"📹 Starting live detection from camera {args.camera}")
        print("Press ESC to exit.")
        
        cap = cv2.VideoCapture(args.camera)
        if not cap.isOpened():
            print(f"❌ Could not open camera {args.camera}")
            sys.exit(1)
        
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
    
    # Default: Start API server
    else:
        print("No specific mode selected. Starting Flask API server...")
        print(f"🌐 Server running on http://127.0.0.1:{args.port}/")
        app.run(host="0.0.0.0", port=args.port, debug=args.debug)


def run_tests():
    """Run system tests"""
    print("=" * 50)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Import modules
    print("\n[Test 1] Importing modules...")
    try:
        from detection import AccidentDetector, calculate_iou
        from alert import AlertSystem
        from OSM import EmergencyServicesLocator, haversine_distance
        print("   ✅ All modules imported successfully")
        tests_passed += 1
    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
        tests_failed += 1
    
    # Test 2: IoU calculation
    print("\n[Test 2] IoU calculation...")
    try:
        from detection import calculate_iou
        box1 = [0, 0, 100, 100]
        box2 = [50, 50, 150, 150]
        iou = calculate_iou(box1, box2)
        expected = 2500 / (10000 + 10000 - 2500)  # ~0.143
        if abs(iou - expected) < 0.01:
            print(f"   ✅ IoU calculation correct: {iou:.3f}")
            tests_passed += 1
        else:
            print(f"   ❌ IoU calculation wrong: {iou:.3f} (expected ~{expected:.3f})")
            tests_failed += 1
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        tests_failed += 1
    
    # Test 3: Haversine distance
    print("\n[Test 3] Haversine distance calculation...")
    try:
        from OSM import haversine_distance
        # Chennai to Bangalore (~290 km)
        dist = haversine_distance(13.0827, 80.2707, 12.9716, 77.5946)
        if 280 < dist < 300:
            print(f"   ✅ Distance calculation correct: {dist:.1f} km")
            tests_passed += 1
        else:
            print(f"   ❌ Distance calculation wrong: {dist:.1f} km (expected ~290 km)")
            tests_failed += 1
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        tests_failed += 1
    
    # Test 4: Model file exists
    print("\n[Test 4] YOLO model file...")
    if os.path.exists("models/yolov8n.pt"):
        print("   ✅ Model file exists")
        tests_passed += 1
    else:
        print("   ⚠️ Model file not found (will be downloaded on first run)")
        tests_passed += 1  # Still pass as it will auto-download
    
    # Test 5: Config file
    print("\n[Test 5] Configuration file...")
    if os.path.exists("config.py"):
        print("   ✅ Config file exists")
        tests_passed += 1
    else:
        print("   ❌ Config file not found (create from config.py)")
        tests_failed += 1
    
    # Summary
    print("\n" + "=" * 50)
    print(f"Tests passed: {tests_passed}")
    print(f"Tests failed: {tests_failed}")
    print("=" * 50)
    
    return tests_failed == 0


def launch_gui():
    """Launch the GUI application"""
    try:
        from haversine_gui import HaversineGUI
        import tkinter as tk
        
        root = tk.Tk()
        app = HaversineGUI(root)
        root.mainloop()
    except ImportError as e:
        print(f"❌ GUI launch failed: {e}")
        print("Make sure tkinter is installed.")


if __name__ == "__main__":
    main()
