from flask import Flask, jsonify
import subprocess, threading, requests, socket, time, os, re
from pyngrok import ngrok

app = Flask(__name__)

# Your laptop Node.js hosts
LAPTOP_HOSTS = [
    "desktop-r98pm6a.local",
    "192.168.100.15",
    "10.191.254.91",
    "172.27.44.17"
]

PORT = 5000
RTSP_PORT = 8554
NGROK_PATH = "/usr/local/bin/ngrok"
CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"
CAM_DEVICE = "/dev/video0"

# ------------------------------------------------------
# 🎥 Start RTSP stream using hardware H.264 encoder
# ------------------------------------------------------
def start_rtsp_stream():
    print("🎥 Starting RTSP stream (H.264, 720p @ 15fps)...")

    # Kill existing ffmpeg instances (if any)
    os.system("pkill -f ffmpeg || true")

    ffmpeg_cmd = [
        "ffmpeg",
        "-f", "v4l2",
        "-framerate", "15",
        "-video_size", "1280x720",
        "-i", CAM_DEVICE,
        "-c:v", "h264_v4l2m2m",
        "-b:v", "3M",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-f", "rtsp",
        f"rtsp://0.0.0.0:{RTSP_PORT}/live.stream"
    ]

    subprocess.Popen(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"✅ RTSP stream running at rtsp://<raspi_ip>:{RTSP_PORT}/live.stream")

# ------------------------------------------------------
# 🌩️ Tunnel Management
# ------------------------------------------------------
def get_local_ip():
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
    """Send tunnel URL to Node.js server."""
    for host in LAPTOP_HOSTS:
        try:
            url = f"http://{host}:3000/update-domain"
            print(f"📡 Sending RTSP URL to {url}")
            requests.post(url, json={"url": domain}, timeout=5)
            print(f"✅ Sent successfully to {host}")
            return
        except Exception as e:
            print(f"⚠️ Failed to send to {host}: {e}")
    print("❌ Could not reach any laptop host.")


def start_ngrok():
    print("🚀 Starting Ngrok tunnel (172.27.* network)...")
    public_url = ngrok.connect(RTSP_PORT, "tcp")
    print(f"🌍 Ngrok TCP URL: {public_url}")
    send_domain_to_laptop(str(public_url))


def start_cloudflare():
    print("🌩️ Starting Cloudflare tunnel (normal network)...")
    process = subprocess.Popen(
        [CLOUDFLARED_PATH, "tunnel", "--no-autoupdate", "--url", f"rtsp://localhost:{RTSP_PORT}"],
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


def start_tunnel():
    ip = get_local_ip()
    print(f"🌐 Detected IP: {ip}")
    if ip.startswith("172.27."):
        start_ngrok()
    else:
        start_cloudflare()


# ------------------------------------------------------
# 🧠 Flask server for monitoring
# ------------------------------------------------------
@app.route('/status')
def status():
    return jsonify({"status": "ok", "message": "RTSP stream active"})


if __name__ == "__main__":
    threading.Thread(target=start_rtsp_stream, daemon=True).start()
    threading.Thread(target=start_tunnel, daemon=True).start()

    print(f"✅ Starting Flask server on 0.0.0.0:{PORT}")
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
