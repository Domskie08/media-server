from flask import Flask, Response
import cv2, socket, os, threading, logging, time

# Suppress Flask logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

# --- Camera setup (1280x720 = 720p) ---
camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
camera.set(cv2.CAP_PROP_FPS, 30)
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

# --- Threaded capture ---
latest_frame = None
frame_lock = threading.Lock()

def capture_loop():
    global latest_frame
    while True:
        success, frame = camera.read()
        if not success:
            time.sleep(0.05)
            continue
        with frame_lock:
            latest_frame = frame

# Start background capture thread
threading.Thread(target=capture_loop, daemon=True).start()

@app.route("/ping")
def ping():
    return "pong"

def gen_frames():
    global latest_frame
    while True:
        with frame_lock:
            if latest_frame is None:
                continue
            ret, buffer = cv2.imencode(".jpg", latest_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
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
    app.run(host="0.0.0.0", port=5000, threaded=True)
