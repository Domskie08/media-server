from flask import Flask, send_from_directory, jsonify
import cv2, subprocess, threading, os, socket, requests, re, time

app = Flask(__name__)

# 🧠 Laptop IPs (for domain sync)
LAPTOP_HOSTS = [
    "desktop-r98pm6a.local",
    "192.168.100.15",
    "10.191.254.91",
    "172.27.44.73"
]

PORT = 5000
CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"

# 📁 Folder for HLS files
HLS_DIR = "hls"
os.makedirs(HLS_DIR, exist_ok=True)

# 🎥 Start ffmpeg process to stream camera → HLS
def start_ffmpeg_stream():
    print("🎥 Starting H.264 → HLS stream...")
    ffmpeg_cmd = [
        "ffmpeg",
        "-f", "v4l2",              # Capture from camera
        "-input_format", "h264",   # Hardware encoding (use mjpeg if unsupported)
        "-video_size", "1280x720",
        "-i", "/dev/video0",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-f", "hls",
        "-hls_time", "2",          # 2s per segment
        "-hls_list_size", "4",
        "-hls_flags", "delete_segments",
        f"{HLS_DIR}/index.m3u8"
    ]
    subprocess.Popen(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

# 🛰 Serve the HLS files
@app.route('/hls/<path:filename>')
def serve_hls(filename):
    return send_from_directory(HLS_DIR, filename)

@app.route('/status')
def status():
    return jsonify({"status": "ok", "stream": f"/hls/index.m3u8"})

# 🌩 Auto-tunnel via Ngrok (or Cloudflare fallback)
def start_tunnel():
    print("🌩 Starting Ngrok tunnel...")
    try:
        process = subprocess.Popen(
            ["ngrok", "http", str(PORT), "--log", "stdout"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )

        for line in process.stdout:
            match = re.search(r"https://[a-z0-9\-]+\.ngrok-free\.app", line)
            if match:
                domain = match.group(0)
                print(f"🌍 Ngrok URL: {domain}")
                send_domain_to_laptop(domain)
                break
    except Exception as e:
        print(f"⚠️ Tunnel error: {e}")

def send_domain_to_laptop(domain):
    for host in LAPTOP_HOSTS:
        try:
            url = f"http://{host}:3000/update-domain"
            print(f"📡 Sending stream URL to {url}")
            requests.post(url, json={"url": domain}, timeout=5)
            print(f"✅ Sent successfully to {host}")
            return
        except Exception as e:
            print(f"⚠️ Failed to send to {host}: {e}")
    print("❌ Could not reach any laptop host.")

# 🧠 Startup
if __name__ == "__main__":
    threading.Thread(target=start_ffmpeg_stream, daemon=True).start()
    threading.Thread(target=start_tunnel, daemon=True).start()

    hostname = socket.gethostname()
    print(f"✅ Flask HLS server on http://{hostname}.local:{PORT}")
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
