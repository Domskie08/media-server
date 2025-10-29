from flask import Flask, Response, jsonify
import cv2, subprocess, re, requests, socket, time, threading, os
from pyngrok import ngrok  # make sure to install pyngrok: pip install pyngrok

app = Flask(__name__)

# -------------------------------
# Configuration
# -------------------------------
LAPTOP_HOSTS = [
    "desktop-r98pm6a.local",  # hostname
    "192.168.100.15",         # fallback IP
    "10.191.254.91",
    "172.27.44.17"
]

PORT = 5000
CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"

# -------------------------------
# Open camera
# -------------------------------
camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"H264"))
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
camera.set(cv2.CAP_PROP_FPS, 30)

def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            print("⚠️ No camera feed detected.")
            time.sleep(1)
            continue
        _, buffer = cv2.imencode('.jpg', frame)  # still sending MJPEG
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    return jsonify({"status": "ok", "message": "Raspberry Pi camera is running"})

# -------------------------------
# Tunnel / Network
# -------------------------------
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
            print(f"📡 Sending public URL to {url}")
            requests.post(url, json={"url": domain}, timeout=5)
            print(f"✅ Sent successfully to {host}")
            return
        except Exception as e:
            print(f"⚠️ Failed to send to {host}: {e}")
    print("❌ Could not reach any laptop host.")

def start_ngrok():
    try:
        url = ngrok.connect(PORT)
        print(f"🌍 Ngrok public URL: {url}")
        send_domain_to_laptop(url)
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
    except FileNotFoundError:
        print("❌ cloudflared not found at /usr/local/bin/cloudflared.")
    except Exception as e:
        print(f"⚠️ Cloudflare error: {e}")

def start_tunnel():
    ip = get_local_ip()
    print(f"🌐 Detected Pi LAN IP: {ip}")
    if ip.startswith("172.27."):
        print("🚀 Using Ngrok (corporate LAN detected)")
        start_ngrok()
    else:
        print("🌩️ Using Cloudflare")
        start_cloudflare()

# -------------------------------
# Startup
# -------------------------------
if __name__ == "__main__":
    threading.Thread(target=start_tunnel, daemon=True).start()
    hostname = socket.gethostname()
    print(f"✅ Starting camera server on http://{hostname}.local:{PORT}")
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
