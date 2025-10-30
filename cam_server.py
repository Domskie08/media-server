from flask import Flask, Response, jsonify
import cv2, threading, subprocess, socket, requests, re, os
from pyngrok import ngrok

app = Flask(__name__)

# Laptop Node.js server possible hosts
LAPTOP_HOSTS = [
    "desktop-r98pm6a.local",
    "192.168.100.15",
    "10.191.254.91",
    "172.27.44.17"
]

PORT = 5000
CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"
CAM_ID = 0  # Usually /dev/video0

# -------------------------------
# Utility functions
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
    """Send the streaming domain to all known laptop hosts"""
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


# -------------------------------
# Video stream generator
# -------------------------------
def generate_frames():
    cap = cv2.VideoCapture(CAM_ID)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)
    cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        raise RuntimeError("❌ Cannot open camera")

    print("🎥 Camera streaming started...")

    while True:
        success, frame = cap.read()
        if not success:
            break
        _, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


@app.route('/video_feed')
def video_feed():
    """Live MJPEG feed"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/status')
def status():
    return jsonify({"status": "ok", "message": "Live stream active"})


# -------------------------------
# Tunnel Logic (Ngrok / Cloudflare)
# -------------------------------
def start_cloudflare_tunnel():
    print("🌩️ Starting Cloudflare tunnel...")
    process = subprocess.Popen(
        [CLOUDFLARED_PATH, "tunnel", "--no-autoupdate", "--url", f"http://localhost:{PORT}"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    for line in process.stdout:
        line = line.strip()
        if "trycloudflare.com" in line:
            match = re.search(r"https://[^\s]+trycloudflare\.com", line)
            if match:
                url = match.group(0)
                print(f"✅ Cloudflare URL: {url}")
                send_domain_to_laptop(url + "/video_feed")
                break


def start_ngrok_tunnel():
    print("🚀 Starting Ngrok tunnel...")
    public_url = ngrok.connect(PORT, "http").public_url
    print(f"✅ Ngrok URL: {public_url}")
    send_domain_to_laptop(public_url + "/video_feed")


def start_connection_mode():
    ip = get_local_ip()
    print(f"🌐 Detected local IP: {ip}")

    if ip.startswith("172.27.44."):
        print("🏢 Office Network Detected → Ngrok Mode")
        start_ngrok_tunnel()
    else:
        print("🏠 Home Network Detected → Cloudflare Mode")
        try:
            start_cloudflare_tunnel()
        except Exception as e:
            print(f"⚠️ Cloudflare failed ({e}), using Ngrok instead")
            start_ngrok_tunnel()


# -------------------------------
# Main Entry
# -------------------------------
if __name__ == "__main__":
    threading.Thread(target=start_connection_mode, daemon=True).start()

    print(f"✅ Flask camera server running on port {PORT}")
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
