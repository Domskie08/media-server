from flask import Flask, Response, jsonify
import cv2, subprocess, re, requests, socket, time, threading, os, shutil

app = Flask(__name__)

# 🧠 Laptop hostnames/IPs (where your media.js server runs)
LAPTOP_HOSTS = [
    "desktop-r98pm6a.local",
    "192.168.100.15",
    "10.191.254.91",
    "172.27.44.17"
]

PORT = 5000
CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"
NGROK_PATH = "/usr/local/bin/ngrok"  # Optional fallback if installed

# 🎥 Initialize camera
camera = cv2.VideoCapture(0)

def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            print("⚠️ No camera feed detected. Retrying...")
            time.sleep(1)
            continue
        _, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    return jsonify({"status": "ok", "message": "Raspberry Pi camera is running"})


# -------------------------------------------------------------------
# 🌩️ AUTO TUNNEL SYSTEM (Cloudflare → fallback to Ngrok)
# -------------------------------------------------------------------
def start_tunnel():
    print("🌩️ Attempting Cloudflare tunnel...")

    if not shutil.which(CLOUDFLARED_PATH):
        print("⚠️ Cloudflared not found — skipping to Ngrok fallback.")
        start_ngrok_tunnel()
        return

    args = [CLOUDFLARED_PATH, "tunnel", "--no-autoupdate", "--protocol", "http2", "--url", f"http://localhost:{PORT}"]
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    success = False
    fail_count = 0

    for line in process.stdout:
        line = line.strip()
        print(line)

        # Retry logic if Cloudflare edge unreachable
        if "timeout" in line.lower() or "failed" in line.lower():
            fail_count += 1
            if fail_count > 5:
                print("⚠️ Too many Cloudflare failures, switching to Ngrok...")
                process.terminate()
                start_ngrok_tunnel()
                return

        # Detect Cloudflare domain
        match = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", line)
        if match:
            domain = match.group(0)
            print(f"✅ Cloudflare URL: {domain}")
            send_domain_to_laptop(domain)
            success = True
            break

    if not success:
        print("❌ Cloudflare tunnel failed — trying Ngrok...")
        start_ngrok_tunnel()


# -------------------------------------------------------------------
# 🌍 NGROK FALLBACK (Free domain, better for strict networks)
# -------------------------------------------------------------------
def start_ngrok_tunnel():
    if not shutil.which(NGROK_PATH):
        print("❌ Ngrok not installed — please install it manually.")
        print("   👉 sudo apt install unzip -y && curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | "
              "sudo tee /etc/apt/trusted.gpg.d/ngrok.asc > /dev/null && "
              "echo 'deb https://ngrok-agent.s3.amazonaws.com buster main' | sudo tee /etc/apt/sources.list.d/ngrok.list && "
              "sudo apt update && sudo apt install ngrok -y")
        return

    print("🌍 Starting Ngrok tunnel...")
    process = subprocess.Popen(
        [NGROK_PATH, "http", str(PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    # Wait a few seconds before checking tunnel info
    time.sleep(5)
    try:
        tunnel_info = requests.get("http://127.0.0.1:4040/api/tunnels").json()
        public_url = tunnel_info["tunnels"][0]["public_url"]
        print(f"✅ Ngrok URL: {public_url}")
        send_domain_to_laptop(public_url)
    except Exception as e:
        print(f"⚠️ Could not retrieve Ngrok URL: {e}")


# -------------------------------------------------------------------
# 📡 Send the public URL to laptop
# -------------------------------------------------------------------
def send_domain_to_laptop(domain):
    for host in LAPTOP_HOSTS:
        try:
            url = f"http://{host}:3000/update-domain"
            print(f"📡 Sending URL to {url}")
            res = requests.post(url, json={"url": domain}, timeout=5)
            if res.status_code == 200:
                print(f"✅ Sent successfully to {host}")
                return
        except Exception as e:
            print(f"⚠️ Failed to send to {host}: {e}")
    print("❌ Could not reach any laptop host.")


# -------------------------------------------------------------------
# 🧠 STARTUP
# -------------------------------------------------------------------
if __name__ == "__main__":
    threading.Thread(target=start_tunnel, daemon=True).start()
    hostname = socket.gethostname()
    print(f"✅ Raspberry Pi camera server on http://{hostname}.local:{PORT}")
    from waitress import serve
    serve(app, host="0.0.0.0", port=PORT)
