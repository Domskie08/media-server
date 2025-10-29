from flask import Flask, Response, jsonify
import subprocess, re, requests, socket, threading, os, time
from pyngrok import ngrok

app = Flask(__name__)

# -------------------------------
# Configuration
# -------------------------------
LAPTOP_HOSTS = [
    "desktop-r98pm6a.local",
    "192.168.100.15",
    "10.191.254.91",
    "172.27.44.17"
]

PORT = 5000
CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"
NGROK_PATH = "/usr/local/bin/ngrok"

# HLS output folder
HLS_DIR = os.path.join(os.getcwd(), "hls")
os.makedirs(HLS_DIR, exist_ok=True)

# -------------------------------
# Start FFmpeg H.264 -> HLS
# -------------------------------
def start_h264_hls():
    print("🎥 Starting H.264 camera -> HLS stream (1080p30)...")
    ffmpeg_cmd = [
        "ffmpeg",
        "-f", "v4l2",          # video4linux input
        "-framerate", "30",
        "-video_size", "1920x1080",
        "-i", "/dev/video0",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-f", "hls",
        "-hls_time", "1",
        "-hls_list_size", "3",
        "-hls_flags", "delete_segments",
        os.path.join(HLS_DIR, "index.m3u8")
    ]
    subprocess.Popen(ffmpeg_cmd)

# -------------------------------
# Flask routes
# -------------------------------
@app.route('/video_feed')
def video_feed():
    m3u8_path = os.path.join(HLS_DIR, "index.m3u8")
    if not os.path.exists(m3u8_path):
        return "HLS stream not ready yet", 503
    with open(m3u8_path, "r") as f:
        content = f.read()
    return Response(content, mimetype="application/vnd.apple.mpegurl")

@app.route('/status')
def status():
    return jsonify({"status": "ok", "message": "H.264 HLS camera is running"})

# -------------------------------
# Network / Tunneling
# -------------------------------
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
            requests.post(url, json={"url": str(domain)}, timeout=5)
            print(f"✅ Sent successfully to {host}")
            return
        except Exception as e:
            print(f"⚠️ Failed to send to {host}: {e}")
    print("❌ Could not reach any laptop host.")

def start_ngrok():
    try:
        tunnel = ngrok.connect(PORT, "http")  # returns NgrokTunnel object
        public_url = tunnel.public_url       # ✅ convert to string
        print(f"🌍 Ngrok public URL: {public_url}")
        send_domain_to_laptop(public_url)
    except Exception as e:
        print(f"❌ Ngrok error: {e}")

def start_cloudflare():
    try:
        home_dir = os.path.expanduser("~")
        process = subprocess.Popen(
            [CLOUDFLARED_PATH, "tunnel", "--no-autoupdate", "--url", f"http://localhost:{PORT}"],
            cwd=home_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        for line in process.stdout:
            line = line.strip()
            print(line)
            match = re.search(r"https://[^\s]+trycloudflare\.com", line)
            if match:
                domain = match.group(0)
                print(f"🌍 Cloudflare URL: {domain}")
                send_domain_to_laptop(domain)
                break
    except Exception as e:
        print(f"❌ Cloudflare error: {e}")

def start_tunnel():
    ip = get_local_ip()
    print(f"🌐 Detected Pi LAN IP: {ip}")
    if ip.startswith("172.27."):
        print("🚀 Using Ngrok tunnel")
        start_ngrok()
    else:
        print("🌩️ Using Cloudflare tunnel")
        start_cloudflare()

# -------------------------------
# Startup
# -------------------------------
if __name__ == "__main__":
    threading.Thread(target=start_h264_hls, daemon=True).start()
    threading.Thread(target=start_tunnel, daemon=True).start()
    print(f"✅ Starting H.264 HLS camera server on port {PORT}")
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
