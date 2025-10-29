from flask import Flask, Response, jsonify, send_from_directory
import cv2, subprocess, socket, threading, os, time, requests, re

app = Flask(__name__)

# 💻 Laptop hosts (media.js server)
LAPTOP_HOSTS = [
    "desktop-r98pm6a.local",
    "192.168.100.15",
    "10.191.254.91",
    "172.27.44.17"
]

PORT = 5000
HLS_DIR = "hls"  # folder for HLS segments
CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"
NGROK_PATH = "/usr/local/bin/ngrok"

# 🎥 Camera settings (H.264)
CAM_WIDTH = 640
CAM_HEIGHT = 480
FPS = 30

# Make HLS directory
os.makedirs(HLS_DIR, exist_ok=True)

# -----------------------------
# Start HLS streaming via ffmpeg
# -----------------------------
def start_hls():
    """Start ffmpeg H.264 -> HLS"""
    camera = "/dev/video0"  # default Pi camera
    cmd = [
        "ffmpeg",
        "-f", "v4l2",
        "-framerate", "30",
        "-video_size", "1920x1080",
        "-input_format", "mjpeg",
        "-i", "/dev/video0",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-b:v", "4M",
        "-f", "hls",
        "-hls_time", "1",
        "-hls_list_size", "5",
        "-hls_flags", "delete_segments",
        os.path.join(HLS_DIR, "index.m3u8")
    ]
    print("🎥 Starting HLS stream via ffmpeg...")
    subprocess.Popen(cmd)

# -----------------------------
# Flask routes
# -----------------------------
@app.route('/hls/<path:filename>')
def hls_files(filename):
    """Serve HLS .m3u8 and .ts files"""
    return send_from_directory(HLS_DIR, filename)

@app.route('/status')
def status():
    return jsonify({"status": "ok", "message": "Raspberry Pi camera is running"})

# -----------------------------
# Auto tunnel selection
# -----------------------------
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def send_domain_to_laptop(domain):
    for host in LAPTOP_HOSTS:
        try:
            url = f"http://{host}:3000/update-domain"
            print(f"📡 Sending HLS URL to {url}")
            requests.post(url, json={"url": domain}, timeout=5)
            print(f"✅ Sent successfully to {host}")
            return
        except Exception as e:
            print(f"⚠️ Failed to send to {host}: {e}")
    print("❌ Could not reach any laptop host.")

def start_ngrok(port):
    try:
        process = subprocess.Popen(
            [NGROK_PATH, "http", str(port)],
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
        print("❌ Ngrok not found. Install it.")

def start_cloudflare(port):
    try:
        process = subprocess.Popen(
            [CLOUDFLARED_PATH, "tunnel", "--no-autoupdate", "--url", f"http://localhost:{port}"],
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
        print("❌ cloudflared not found.")

def start_tunnel():
    ip = get_local_ip()
    print(f"🌐 Detected Pi LAN IP: {ip}")
    if ip.startswith("172.27."):
        print("🚀 Using NGROK tunnel (corporate network detected)")
        start_ngrok(PORT)
    else:
        print("🌩️ Using CLOUDFLARE tunnel")
        start_cloudflare(PORT)

# -----------------------------
# Startup sequence
# -----------------------------
if __name__ == "__main__":
    threading.Thread(target=start_hls, daemon=True).start()
    threading.Thread(target=start_tunnel, daemon=True).start()

    hostname = socket.gethostname()
    print(f"✅ Starting camera server on http://{hostname}.local:{PORT}")
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
