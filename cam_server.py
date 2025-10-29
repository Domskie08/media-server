from flask import Flask, Response, jsonify
import cv2, subprocess, re, requests, socket, time, threading, os

app = Flask(__name__)

# 🧠 List of laptop IPs/hostnames where media.js runs
LAPTOP_HOSTS = [
    "desktop-r98pm6a.local",
    "192.168.100.15",
    "10.191.254.91",
    "172.27.44.17"
]

PORT = 5000
CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"
NGROK_PATH = "/usr/local/bin/ngrok"

# 🎥 Open webcam (H.264 hardware-accelerated)
camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"H264"))
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
camera.set(cv2.CAP_PROP_FPS, 30)

def generate_frames():
    """Stream frames using H.264 compression."""
    while True:
        success, frame = camera.read()
        if not success:
            print("⚠️ No camera feed detected.")
            time.sleep(1)
            continue

        # encode as JPEG (client compatible)
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue

        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


@app.route('/video_feed')
def video_feed():
    """MJPEG video stream endpoint."""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/status')
def status():
    return jsonify({"status": "ok", "message": "Raspberry Pi camera is running"})


# -------------------------------------------------------------------
# 🌩️ AUTO TUNNEL SYSTEM (Ngrok or Cloudflare)
# -------------------------------------------------------------------

def get_local_ip():
    """Detect the current LAN IP."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def start_tunnel():
    """Auto-select tunnel type."""
    ip = get_local_ip()
    print(f"🌐 Detected IP: {ip}")

    if ip.startswith("172."):
        print("🚀 Using NGROK tunnel (detected 172.* network)")
        start_ngrok()
    else:
        print("🌩️ Using CLOUDFLARE tunnel (default)")
        start_cloudflare()


def start_ngrok():
    """Start Ngrok tunnel."""
    try:
        process = subprocess.Popen(
            [NGROK_PATH, "http", str(PORT)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        for line in process.stdout:
            line = line.strip()
            print(line)
            match = re.search(r"https://[a-z0-9\-]+\.ngrok\-free\.app", line)
            if match:
                domain = match.group(0)
                print(f"\n🌍 Ngrok URL: {domain}\n")
                send_domain_to_laptop(domain)
                break
    except FileNotFoundError:
        print("❌ Ngrok not found. Install it using:")
        print("   sudo apt install ngrok -y")


def start_cloudflare():
    """Start Cloudflare tunnel."""
    try:
        process = subprocess.Popen(
            [CLOUDFLARED_PATH, "tunnel", "--no-autoupdate", "--url", f"http://localhost:{PORT}"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        for line in process.stdout:
            line = line.strip()
            print(line)
            match = re.search(r"https://[^\s]+trycloudflare\.com", line)
            if match:
                domain = match.group(0)
                print(f"\n🌍 Cloudflare URL: {domain}\n")
                send_domain_to_laptop(domain)
                break
    except FileNotFoundError:
        print("❌ Cloudflared not found. Install it using:")
        print("   sudo apt install cloudflared -y")


def send_domain_to_laptop(domain):
    """Send the generated domain to Node.js server."""
    for host in LAPTOP_HOSTS:
        try:
            url = f"http://{host}:3000/update-domain"
            print(f"📡 Sending domain to {url}")
            requests.post(url, json={"url": domain}, timeout=5)
            print(f"✅ Sent successfully to {host}")
            return
        except Exception as e:
            print(f"⚠️ Failed to send to {host}: {e}")
    print("❌ Could not reach any laptop host.")


# -------------------------------------------------------------------
# 🚀 STARTUP SEQUENCE
# -------------------------------------------------------------------
if __name__ == "__main__":
    threading.Thread(target=start_tunnel, daemon=True).start()
    hostname = socket.gethostname()
    print(f"✅ Starting H.264 camera server on http://{hostname}.local:{PORT}")
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
