from flask import Flask, Response, jsonify
import cv2, subprocess, re, requests, socket, time, threading, os

app = Flask(__name__)

# 🧠 Your laptop hostnames or IPs (where media.js runs)
LAPTOP_HOSTS = [
    "desktop-r98pm6a.local",  # hostname
    "192.168.100.15",         # fallback IP
    "10.191.254.91",
     "172.27.44.17"
]

PORT = 5000
CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"  # confirmed path

# 🎥 Open webcam
camera = cv2.VideoCapture(0)

def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            print("⚠️ No camera feed detected.")
            time.sleep(1)
            continue
        _, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    return jsonify({"status": "ok", "message": "Raspberry Pi camera is running"})

# -------------------------------------------------------------------
# 🌩️ CLOUD FLARE AUTO START + SYNC TO LAPTOP
# -------------------------------------------------------------------
def start_cloudflare():
    print("🌩️ Starting Cloudflare Tunnel...")

    def run_cloudflare(use_transport=False):
        args = [CLOUDFLARED_PATH, "tunnel", "--no-autoupdate"]
        if use_transport:
            # Force Cloudflare to use HTTPS only (skip QUIC)
            args += ["--transport", "http2"]
        else:
            # Prefer HTTP/2 but may attempt QUIC first
            args += ["--protocol", "http2"]
        args += ["--url", f"http://localhost:{PORT}"]

        home_dir = os.path.expanduser("~")
        return subprocess.Popen(
            args,
            cwd=home_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

    process = run_cloudflare(use_transport=False)
    quic_fail_count = 0

    for line in process.stdout:
        line = line.strip()
        print(line)

        # 🕵️ Detect QUIC timeout errors
        if "7844" in line and "timeout" in line.lower():
            quic_fail_count += 1
            if quic_fail_count >= 3:
                print("\n⚠️ Detected repeated QUIC failures — restarting tunnel with --transport http2...\n")
                process.terminate()
                time.sleep(3)
                process = run_cloudflare(use_transport=True)
                quic_fail_count = 0
                continue

        # 🌍 Extract public Cloudflare domain
        match = re.search(r"https://[^\s]+trycloudflare\.com", line)
        if match:
            domain = match.group(0).strip()
            print(f"\n🌍 Cloudflare URL: {domain}\n")
            send_domain_to_laptop(domain)

    print("🌩️ Starting Cloudflare Tunnel...")
    try:
        home_dir = os.path.expanduser("~")  # ✅ safely resolves /home/pi or your user folder
        process = subprocess.Popen(
            [CLOUDFLARED_PATH, "tunnel", "--no-autoupdate", "--transport", "http2", "--url", f"http://localhost:{PORT}"],
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
                domain = match.group(0).strip()
                print(f"\n🌍 Cloudflare URL: {domain}\n")
                send_domain_to_laptop(domain)

    except FileNotFoundError:
        print(f"❌ cloudflared not found at {CLOUDFLARED_PATH}. Try reinstalling or checking the path.")
    except Exception as e:
        print(f"⚠️ Error running Cloudflare: {e}")

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
# 🧠 STARTUP SEQUENCE
# -------------------------------------------------------------------
if __name__ == "__main__":
    threading.Thread(target=start_cloudflare, daemon=True).start()

    hostname = socket.gethostname()
    print(f"✅ Starting camera server on http://{hostname}.local:{PORT}")
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
