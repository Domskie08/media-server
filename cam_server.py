from flask import Flask, Response
import cv2, socket, os, logging, time

# Suppress Flask logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

# --- Try to open camera using both drivers ---
def init_camera():
    print("🔍 Checking available video devices...")
    for i in range(3):  # try /dev/video0–2
        if os.path.exists(f"/dev/video{i}"):
            print(f"✅ Found /dev/video{i}")
    print("🎥 Initializing camera...")

    # Try CAP_V4L2 first (legacy driver)
    cam = cv2.VideoCapture(0, cv2.CAP_V4L2)
    time.sleep(1)
    if not cam.isOpened():
        print("⚠️ CAP_V4L2 failed, retrying with default OpenCV backend...")
        cam = cv2.VideoCapture(0)
        time.sleep(1)

    if not cam.isOpened():
        print("❌ Cannot open any camera device. Check connections or enable Legacy Camera in raspi-config.")
        return None

    # Configure for 720 p, 30 fps
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cam.set(cv2.CAP_PROP_FPS, 30)
    cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    print("✅ Camera initialized successfully.")
    return cam

camera = init_camera()

@app.route("/ping")
def ping():
    return "pong"

def gen_frames():
    global camera
    while True:
        if not camera or not camera.isOpened():
            camera = init_camera()
            time.sleep(1)
            continue
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

if __name__ == "__main__":
    print_ips()
    hostname = socket.gethostname()
    print(f"✅ Hostname: {hostname}.local")
    print("🚀 Starting video server at port 5000…")
    app.run(host="0.0.0.0", port=5000)
