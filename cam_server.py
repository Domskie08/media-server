from flask import Flask, Response, jsonify
import subprocess, threading, requests, socket, os, re
from pyngrok import ngrok

app = Flask(__name__)

# Laptop Node.js server hosts
LAPTOP_HOSTS = [
    "desktop-r98pm6a.local",
    "192.168.100.15",
    "10.191.254.91",
    "172.27.44.17"
]

PORT = 5000
CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"

RTSP_URL = "rtsp://localhost:8554/live"  # Local RTSP feed
CAM_DEVICE = "/dev/video0"


# -----------------------
# RTSP Stream (FFmpeg)
# -----------------------
def start_rtsp_stream():
    print("🎥 Starting RTSP stream (libx264, 15fps, 720p)...")
    subprocess.Popen([
        "ffmpeg",
        "-f", "v4l2",
        "-framerate", "15",
        "-video_size", "1280x720",
        "-i", CAM_DEVICE,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-b:v", "2M",
        "-f", "rtsp",
        "-rtsp_transport", "tcp",
        RTSP_URL
    ])


@app.route('/status')
def status():
    return jsonify({"status": "ok", "stream": RTSP_URL})


# -----------------------
# Cloudflare Tunnel
# -----------------------
def get_local_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def send_domain_to_laptop(domain):
    for host in LAPTOP_HOSTS:
        try:
            url = f"http://{host}:3000/update-domain"
            print(f"📡 Sending Cloudflare URL to {url}")
            requests.post(url, json={"url": domain}, timeout=5)
            print(f"✅ Sent successfully to {host}")
            return
        except Exception as e:
            print(f"⚠️ Failed to send to {host}: {e}")
    print("❌ Could not reach any laptop host.")


def start_cloudflare():
    print("🌩️ Starting Cloudflare tunnel (analytics disabled)...")
    process = subprocess.Popen(
        [
            CLOUDFLARED_PATH,
            "tunnel",
            "--no-autoupdate",
            "--disable-analytics",        # ✅ No tracking / CORS issues
            "--no-chunked-encoding",
            "--url", f"http://localhost:{PORT}"
        ],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
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


# -----------------------
# Startup
# -----------------------
if __name__ == "__main__":
    threading.Thread(target=start_rtsp_stream, daemon=True).start()
    threading.Thread(target=start_cloudflare, daemon=True).start()

    print(f"✅ Starting Flask server on 0.0.0.0:{PORT}")
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
