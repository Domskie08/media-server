from flask import Flask, jsonify
import subprocess, re, requests, socket, threading, os, time
from pyngrok import ngrok  # ✅ pyngrok handles tunnel URL retrieval automatically

app = Flask(__name__)

# Node.js server hosts
LAPTOP_HOSTS = [
    "desktop-r98pm6a.local",
    "192.168.100.15",
    "10.191.254.91",
    "172.27.44.17"
]

PORT = 5000
CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"
HLS_OUTPUT = "/home/admin/media-server/hls/index.m3u8"

# -----------------------------
# H.264 HLS Streaming
# -----------------------------
def start_h264_hls():
    os.makedirs(os.path.dirname(HLS_OUTPUT), exist_ok=True)
    ffmpeg_cmd = [
        "ffmpeg",
        "-f", "v4l2",
        "-framerate", "30",
        "-video_size", "1920x1080",  # adjust for full camera resolution
        "-i", "/dev/video0",
        "-c:v", "h264_v4l2m2m",
        "-b:v", "4M",
        "-f", "hls",
        "-hls_time", "2",
        "-hls_list_size", "3",
        "-hls_flags", "delete_segments+append_list",
        HLS_OUTPUT
    ]
    print("🎥 Starting H.264 HLS streaming...")
    return subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


# -----------------------------
# Detect LAN IP
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


# -----------------------------
# Tunnel Management
# -----------------------------
def start_tunnel():
    ip = get_local_ip()
    print(f"🌐 Detected Pi LAN IP: {ip}")

    if ip.startswith("172.27."):
        print("🚀 Using Ngrok tunnel (corporate network)")
        start_ngrok()
    else:
        print("🌩️ Using Cloudflare tunnel")
        start_cloudflare()


def start_ngrok():
    try:
        # ✅ Create Ngrok HTTP tunnel
        public_url = ngrok.connect(PORT, bind_tls=True).public_url
        print(f"\n🌍 Ngrok URL: {public_url}\n")
        send_domain_to_laptop(public_url)
    except Exception as e:
        print(f"❌ Ngrok failed: {e}")


def start_cloudflare():
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
        print(f"❌ cloudflared not found at {CLOUDFLARED_PATH}")


# -----------------------------
# Send tunnel URL to Node.js server
# -----------------------------
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


# -----------------------------
# Flask endpoints
# -----------------------------
@app.route('/status')
def status():
    return jsonify({"status": "ok", "message": "Raspberry Pi H.264 camera streaming"})


# -----------------------------
# Startup
# -----------------------------
if __name__ == "__main__":
    # Start H.264 HLS streaming
    threading.Thread(target=start_h264_hls, daemon=True).start()

    # Start tunnel
    threading.Thread(target=start_tunnel, daemon=True).start()

    hostname = socket.gethostname()
    print(f"✅ Starting camera server on http://{hostname}.local:{PORT}")
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
