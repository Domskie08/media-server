from flask import Flask, Response, jsonify, send_from_directory
import subprocess, threading, requests, socket, time, os, re
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
NGROK_PATH = "/usr/local/bin/ngrok"
CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"

HLS_FOLDER = "/home/admin/media-server/hls"
HLS_INDEX = f"{HLS_FOLDER}/index.m3u8"
CAM_DEVICE = "/dev/video0"

# -----------------------
# Video feed using HLS
# -----------------------
def start_hls_stream():
    os.makedirs(HLS_FOLDER, exist_ok=True)
    print("🎥 Starting HLS stream via FFmpeg (libx264)...")

    ffmpeg_cmd = [
        "ffmpeg",
        "-f", "v4l2",
        "-framerate", "10",          # lower framerate for slow internet
        "-video_size", "640x480",    # lower resolution for smoothness
        "-i", CAM_DEVICE,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-b:v", "1M",
        "-f", "hls",
        "-hls_time", "2",
        "-hls_list_size", "3",
        "-hls_flags", "delete_segments+append_list",
        HLS_INDEX
    ]

    subprocess.Popen(ffmpeg_cmd)

@app.route('/')
def index():
    """Simple HTML player"""
    return '''
    <html>
    <head><title>Raspberry Pi Camera Stream</title></head>
    <body style="background:#000; text-align:center; color:white;">
        <h3>📺 Live Camera Stream</h3>
        <video width="640" height="480" controls autoplay muted>
            <source src="/hls/index.m3u8" type="application/vnd.apple.mpegurl">
            Your browser does not support HLS playback.
        </video>
    </body>
    </html>
    '''

@app.route('/hls/<path:filename>')
def serve_hls(filename):
    return send_from_directory(HLS_FOLDER, filename)

@app.route('/status')
def status():
    return jsonify({"status": "ok", "message": "Raspberry Pi HLS camera is running"})

# -----------------------
# Tunnel management
# -----------------------
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
    for host in LAPTOP_HOSTS:
        try:
            url = f"http://{host}:3000/update-domain"
            print(f"📡 Sending Ngrok URL to {url}")
            requests.post(url, json={"url": domain}, timeout=5)
            print(f"✅ Sent successfully to {host}")
            return
        except Exception as e:
            print(f"⚠️ Failed to send to {host}: {e}")
    print("❌ Could not reach any laptop host.")

def start_ngrok():
    print("🚀 Starting Ngrok tunnel...")
    public_url = ngrok.connect(PORT, "http").public_url
    print(f"🌍 Ngrok URL: {public_url}")
    send_domain_to_laptop(public_url)

def start_cloudflare():
    print("🌩️ Starting Cloudflare tunnel...")
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
            print(f"🌍 Cloudflare URL: {domain}")
            send_domain_to_laptop(domain)
            break

def start_tunnel():
    ip = get_local_ip()
    print(f"🌐 Detected LAN IP: {ip}")
    if ip.startswith("172.27."):
        start_ngrok()
    else:
        start_cloudflare()

# -----------------------
# Startup
# -----------------------
if __name__ == "__main__":
    threading.Thread(target=start_hls_stream, daemon=True).start()
    threading.Thread(target=start_tunnel, daemon=True).start()

    print(f"✅ Starting Flask HLS server on 0.0.0.0:{PORT}")
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
