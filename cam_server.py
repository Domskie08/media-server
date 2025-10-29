from flask import Flask, Response, jsonify
import cv2, subprocess, re, requests, socket, time, threading, os

app = Flask(__name__)

# Laptop hosts (where your media.js runs)
LAPTOP_HOSTS = [
    "desktop-r98pm6a.local",
    "192.168.100.15",
    "10.191.254.91",
    "172.27.44.73"
]

PORT = 5000
CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"
NGROK_PATH = "/usr/bin/ngrok"  # change if different

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
# 🌩️ Start Cloudflare or fallback to Ngrok
# -------------------------------------------------------------------

def start_tunnel():
    print("🌩️ Starting Cloudflare Tunnel...")
    success = start_cloudflare()
    if not success:
        print("\n⚠️ Cloudflare failed, switching to Ngrok...\n")
        start_ngrok()

def start_cloudflare():
    try:
        home_dir = os.path.expanduser("~")
        process = subprocess.Popen(
            [CLOUDFLARED_PATH, "tunnel", "--no-autoupdate", "--protocol", "http2", "--url", f"http://localhost:{PORT}"],
            cwd=home_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        timeout = time.time() + 40  # wait up to 40 seconds
        for line in process.stdout:
            line = line.strip()
            print(line)
            match = re.search(r"https://[^\s]+trycloudflare\.com", line)
            if match:
                domain = match.group(0).strip()
                print(f"\n✅ Cloudflare Tunnel URL: {domain}\n")
                send_domain_to_laptop(domain)
                return True

            # ⏰ Timeout
            if time.time() > timeout:
                print("⏳ Cloudflare connection timeout.")
                process.terminate()
                return False

    except Exception as e:
        print(f"⚠️ Cloudflare error: {e}")
        return False
    return False

def start_ngrok():
    try:
        print("🚀 Starting Ngrok tunnel...")
        subprocess.run(["pkill", "ngrok"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        process = subprocess.Popen(
            [NGROK_PATH, "http", str(PORT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        time.sleep(5)
        # Get ngrok public URL via API
        import json, urllib.request
        with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels") as resp:
            data = json.load(resp)
            domain = data["tunnels"][0]["public_url"]
            print(f"\n✅ Ngrok Tunnel URL: {domain}\n")
            send_domain_to_laptop(domain)
    except Exception as e:
        print(f"❌ Failed to start Ngrok: {e}")

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

# -------------------------------------------------------------------
# 🧠 STARTUP SEQUENCE
# -------------------------------------------------------------------
if __name__ == "__main__":
    threading.Thread(target=start_tunnel, daemon=True).start()
    hostname = socket.gethostname()
    print(f"✅ Starting camera server on http://{hostname}.local:{PORT}")
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
