from flask import Flask, Response, jsonify
import cv2, subprocess, re, requests, socket, threading, time, os

app = Flask(__name__)

# Laptop hostnames/IPs where media.js runs
LAPTOP_HOSTS = [
    "desktop-r98pm6a.local",  # hostname
    "172.27.44.73",            # your laptop IP
]

PORT = 5000
CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"
NGROK_PATH = "/usr/local/bin/ngrok"

# -----------------------------
# H.264 Camera setup
# -----------------------------
camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"H264"))
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
camera.set(cv2.CAP_PROP_FPS, 30)

def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            print("⚠️ No camera feed detected.")
            time.sleep(1)
            continue
        _, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    return jsonify({"status": "ok", "message": "Raspberry Pi camera is running"})

# -----------------------------
# Helper: Get Pi LAN IP
# -----------------------------
def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

# -----------------------------
# Auto-update Node.js server
# -----------------------------
def send_domain_to_laptop(domain):
    for host in LAPTOP_HOSTS:
        try:
            url = f"http://{host}:3000/update-domain"
            print(f"📡 Sending URL to {url}")
            requests.post(url, json={"url": domain}, timeout=5)
            print(f"✅ Sent successfully to {host}")
            return
        except Exception as e:
            print(f"⚠️ Failed to send to {host}: {e}")
    print("❌ Could not reach any laptop host.")

# -----------------------------
# Tunnel selection
# -----------------------------
def start_tunnel():
    ip = get_lan_ip()
    print(f"🌐 Detected Pi LAN IP: {ip}")

    if ip.startswith("172.27."):
        print("🚀 Using NGROK tunnel (corporate network detected)")
        start_ngrok(ip)
    else:
        print("🌩️ Using Cloudflare tunnel")
        start_cloudflare(ip)

def start_ngrok():
    """Start Ngrok tunnel and forward domain to laptop."""
    try:
        process = subprocess.Popen(
            [NGROK_PATH, "http", str(PORT), "--log", "stdout"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )

        for line in process.stdout:
            line = line.strip()
            print(line)  # Shows Ngrok logs in your terminal

            # Look for the public HTTPS URL
            match = re.search(r"https://[0-9a-z\-]+\.ngrok\.app", line)
            if match:
                domain = match.group(0)
                print(f"\n🌍 Ngrok URL detected: {domain}\n")
                send_domain_to_laptop(domain)
                break  # stop reading once URL is found

    except FileNotFoundError:
        print(f"❌ Ngrok not found at {NGROK_PATH}. Make sure it is installed and executable.")


def start_cloudflare(ip):
    try:
        process = subprocess.Popen(
            [CLOUDFLARED_PATH, "tunnel", "--no-autoupdate", "--url", f"http://{ip}:{PORT}"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        for line in process.stdout:
            print(line.strip())
            match = re.search(r"https://[^\s]+trycloudflare\.com", line)
            if match:
                domain = match.group(0)
                print(f"🌍 Cloudflare URL: {domain}")
                send_domain_to_laptop(domain)
                break
    except FileNotFoundError:
        print("❌ cloudflared not found!")

# -----------------------------
# Startup
# -----------------------------
if __name__ == "__main__":
    threading.Thread(target=start_tunnel, daemon=True).start()
    hostname = socket.gethostname()
    print(f"✅ Starting camera server on http://{hostname}.local:{PORT}")
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
