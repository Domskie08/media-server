from flask import Flask, Response, jsonify, send_from_directory
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
# Start H.264 HLS streaming via FFmpeg
# -------------------------------
def start_h264_hls():
    print("🎥 Starting H.264 camera -> HLS stream (1080p30 hardware)...")
    ffmpeg_cmd = [
        "ffmpeg",
        "-f", "v4l2",
        "-framerate", "30",
        "-video_size", "1280x720",
        "-i", "/dev/video0",
        "-c:v", "h264_omx",          # Hardware-accelerated H.264
        "-b:v", "4M",
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
    # The browser/player will request segments automatically
    return send_from_directory(HLS_DIR, "index.m3u8", mimetype="application/vnd.apple.mpegurl")

@app.route('/hls/<path:filename>')
def hls_files(filename):
    return send_from_directory(HLS_DIR, filename)

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
        tunnel = ngrok.connect(PORT, "http")
        public_url = tunnel.public_url
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
    # Start camera HLS stream in background
    threading.Thread(target=start_h264_hls, daemon=True).start()

    # Start tunneling in background
    threading.Thread(target=start_tunnel, daemon=True).start()

    print(f"✅ Starting H.264 HLS camera server on port {PORT}")
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
