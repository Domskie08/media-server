from flask import Flask, send_from_directory, jsonify
import cv2, subprocess, threading, os, time, re, requests, socket, signal

app = Flask(__name__)

PORT = 5000
CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"
VIDEO_DIR = "static/hls"
os.makedirs(VIDEO_DIR, exist_ok=True)

LAPTOP_HOSTS = [
    "desktop-r98pm6a.local",
    "192.168.100.15",
    "10.191.254.91",
    "172.27.44.17"
]

current_tunnel_domain = None
ffmpeg_process = None


# -------------------------------------------------------------------
# 🎥 FFmpeg H.264 Stream (Auto-restart if fails)
# -------------------------------------------------------------------
def start_ffmpeg_stream():
    global ffmpeg_process
    while True:
        try:
            print("🎥 Starting FFmpeg H.264 stream...")
            # Kill any old FFmpeg
            subprocess.run("pkill -f ffmpeg", shell=True)
            time.sleep(1)

            ffmpeg_cmd = [
                "ffmpeg",
                "-f", "v4l2",
                "-framerate", "30",
                "-video_size", "640x480",
                "-i", "/dev/video0",
                "-vcodec", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-f", "hls",
                "-hls_time", "2",
                "-hls_list_size", "5",
                "-hls_flags", "delete_segments",
                os.path.join(VIDEO_DIR, "index.m3u8")
            ]

            ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Wait & monitor
            while True:
                time.sleep(5)
                if ffmpeg_process.poll() is not None:
                    print("⚠️ FFmpeg stopped — restarting...")
                    break

                if not os.path.exists(os.path.join(VIDEO_DIR, "index.m3u8")):
                    print("⚠️ No HLS output found — restarting FFmpeg...")
                    break

        except Exception as e:
            print(f"❌ FFmpeg error: {e}")
        time.sleep(3)  # delay before retry


def get_local_ip():
    """Detect current LAN IP."""
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
    """Auto-select tunnel: Ngrok for 172.27.*, Cloudflare otherwise."""
    ip = get_local_ip()
    print(f"🌐 Detected IP: {ip}")

    if ip.startswith("172.27."):
        print("🚀 Using NGROK tunnel (corporate network detected)")
        start_ngrok()
    else:
        print("🌩️ Using CLOUDFLARE tunnel (normal network)")
        start_cloudflare()


def start_ngrok():
    """Start Ngrok tunnel and forward domain to laptop."""
    try:
        process = subprocess.Popen(
            [NGROK_PATH, "http", str(PORT)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        for line in process.stdout:
            print(line.strip())
            match = re.search(r"https://[a-z0-9\-]+\.ngrok\-free\.app", line)
            if match:
                domain = match.group(0)
                print(f"\n🌍 Ngrok URL: {domain}\n")
                send_domain_to_laptop(domain)
                break
    except FileNotFoundError:
        print("❌ Ngrok not found at /usr/local/bin/ngrok. Install it with:")
        print("   curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc > /dev/null")
        print("   echo 'deb https://ngrok-agent.s3.amazonaws.com buster main' | sudo tee /etc/apt/sources.list.d/ngrok.list")
        print("   sudo apt update && sudo apt install ngrok -y")


def start_cloudflare():
    """Start Cloudflare tunnel as fallback."""
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


# -------------------------------------------------------------------
# 🌐 Flask Routes
# -------------------------------------------------------------------
@app.route('/hls/<path:filename>')
def serve_hls(filename):
    return send_from_directory(VIDEO_DIR, filename)

@app.route('/status')
def status():
    running = ffmpeg_process and ffmpeg_process.poll() is None
    return jsonify({
        "status": "ok" if running else "error",
        "message": "HLS stream running" if running else "FFmpeg not active"
    })


# -------------------------------------------------------------------
# 🧠 Startup Sequence
# -------------------------------------------------------------------
if __name__ == "__main__":
    threading.Thread(target=start_ffmpeg_stream, daemon=True).start()
    threading.Thread(target=start_tunnel, daemon=True).start()

    hostname = socket.gethostname()
    print(f"✅ Running Flask + HLS on http://{hostname}.local:{PORT}")

    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
