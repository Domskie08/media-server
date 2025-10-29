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


# -------------------------------------------------------------------
# 🌩️ Cloudflare Tunnel (auto start + send URL)
# -------------------------------------------------------------------
def start_cloudflare():
    global current_tunnel_domain
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
            if domain != current_tunnel_domain:
                current_tunnel_domain = domain
                print(f"\n🌍 Cloudflare URL: {domain}\n")
                send_domain_to_laptop(domain)


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
    threading.Thread(target=start_cloudflare, daemon=True).start()

    hostname = socket.gethostname()
    print(f"✅ Running Flask + HLS on http://{hostname}.local:{PORT}")

    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
