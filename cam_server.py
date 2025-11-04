from flask import Flask, Response
import cv2, socket, os, subprocess, time, logging

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

# ============================================================
# 🔍 CAMERA + SYSTEM DIAGNOSTICS
# ============================================================

def run_diagnostics():
    print("🔍 Running Raspberry Pi Camera Diagnostics...\n")

    # ---- Check Power ----
    print("⚡ Checking power status...")
    try:
        result = subprocess.check_output(["vcgencmd", "get_throttled"]).decode().strip()
        if "0x0" in result:
            print("✅ Power OK (no throttling detected)")
        else:
            print(f"⚠️ Power or voltage issue detected! ({result})")
            print("   → Use 5V 3A power supply or shorter USB cable")
    except Exception:
        print("⚠️ Could not read power status — vcgencmd not found")
    print()

    # ---- Check USB devices ----
    print("🔌 Checking USB camera devices...")
    try:
        result = subprocess.check_output(["v4l2-ctl", "--list-devices"]).decode()
        print(result)
    except Exception:
        print("⚠️ Cannot list video devices. Try installing v4l-utils:")
        print("   sudo apt install v4l-utils")
    print()

    # ---- Driver check ----
    print("🧩 Checking camera drivers...")
    try:
        result = subprocess.check_output(["lsmod"]).decode()
        if "bcm2835_v4l2" in result:
            print("✅ Legacy V4L2 driver active (good for OpenCV)")
        elif "videobuf2" in result:
            print("⚠️ libcamera driver active — may cause delay with OpenCV")
            print("   → Run: sudo raspi-config → Interface Options → Legacy Camera → Enable")
        else:
            print("❌ No camera driver found — reinstall camera support")
    except Exception:
        print("⚠️ Unable to check drivers")
    print()

    # ---- Temperature ----
    print("🌡️ Checking temperature...")
    try:
        temp = subprocess.check_output(["vcgencmd", "measure_temp"]).decode().strip()
        print(f"✅ {temp}")
    except:
        print("⚠️ Temperature check unavailable")
    print()

    print("🎥 Testing camera with OpenCV...")
    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        print("❌ Cannot open /dev/video0 — camera not accessible")
    else:
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cam.set(cv2.CAP_PROP_FPS, 15)
        for i in range(3):
            ret, frame = cam.read()
            if not ret:
                print(f"⚠️ Frame {i+1}: capture failed")
            else:
                h, w = frame.shape[:2]
                print(f"✅ Frame {i+1}: OK ({w}x{h})")
            time.sleep(0.5)
        cam.release()
    print("\n✅ Diagnostics complete.\n")

# ============================================================
# 🎥 FLASK VIDEO STREAM
# ============================================================

camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
camera.set(cv2.CAP_PROP_FPS, 15)

@app.route("/ping")
def ping():
    return "pong"

def gen_frames():
    while True:
        success, frame = camera.read()
        if not success:
            continue
        ret, buffer = cv2.imencode(".jpg", frame)
        frame = buffer.tobytes()
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")

@app.route("/video_feed")
def video_feed():
    return Response(gen_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

def print_ips():
    os.system("hostname -I > /tmp/iplist.txt")
    with open("/tmp/iplist.txt") as f:
        ips = f.read().strip().split()
    print("✅ Raspberry Pi IPs:", ips)
    return ips

# ============================================================
# 🚀 MAIN
# ============================================================

if __name__ == "__main__":
    print_ips()
    hostname = socket.gethostname()
    print(f"✅ Hostname: {hostname}.local\n")

    # Run diagnostics once before starting
    run_diagnostics()

    print("🌐 Starting video server on port 5000...\n")
    app.run(host="0.0.0.0", port=5000)
