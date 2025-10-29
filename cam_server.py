from flask import Flask, Response, jsonify
import cv2, subprocess, re, requests, socket, time, threading, os

app = Flask(__name__)

# 🧠 Your laptop hostnames or IPs (where media.js runs)
LAPTOP_HOSTS = [
    "desktop-r98pm6a.local",  # hostname
    "192.168.100.15",         # fallback IP
    "10.191.254.91",
    "172.27.44.73"
]

PORT = 5000
CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"
NGROK_PATH = "/usr/local/bin/ngrok"

# 🎥 Webcam stream setup
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
# 🌩️ CLOUD FLARE + NGROK AUTO START
# -------------------------------------------------------------------
def start_tunnel():
    """Try Cloudflare first; if blocked, use Ngrok fallback."""
    print("🌩️ Attempting Cloudflare Tunnel first...")

    def run_cloudflare():
        home_dir = os.path.expanduser("~")
        return subprocess.Popen(
            [CLOUDFLARED_PATH, "tunnel", "--no-autoupdate", "--protocol", "http2", "--url", f"http://localhost:{PORT}"],
            cwd=home_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

    process = run_cloudflare()
    quic_fail_count = 0
    domain = None

    for line in process.stdout:
        line = line.strip()
        print(line)

        # Detect repeated timeouts on port 7844
        if "7844" in line and "timeout" in line.lower():
            quic_fail_count += 1
            if quic_fail_count >= 3:
                print("\n⚠️ Cloudflare seems blocked (port 7844 timeout). Switching to Ngrok...\n")
                process.terminate()
                return start_ngrok()  # fallback to Ngrok

        # If Cloudflare URL detected
        match = re.search(r"https://[^\s]+trycloudflare\.com", line)
        if match:
            domain = match.group(0).strip()
            print(f"🌍 Cloudflare Tunnel active: {domain}")
            send_domain_to_laptop(domain)
            return

    print("❌ Cloudflare failed to start — switching to Ngrok.")
    return start_ngrok()

def start_ngrok():
    """Start Ngrok tunnel (port 443 HTTPS tunnel)."""
    print("🧠 Starting Ngrok tunnel (port 443)...")
    try:
        subprocess.Popen([NGROK_PATH, "http", str(PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(5)
        result = subprocess.run(["curl", "-s", "http://127.0.0.1:4040/api/tunnels"], capture_output=True, text=True)
        match = re.search(r"https://[^\"]+\.ngrok-free\.app", result.stdout)
        if match:
            url = match.group(0)
            print(f"🌍 Ngrok Tunnel active: {url}")
            send_domain_to_laptop(url)
        else:
            print("⚠️ Could not detect Ngrok URL. Run `ngrok http 5000` manually to check.")
    except FileNotFoundError:
        print(f"❌ Ngrok not found at {NGROK_PATH}. Please install with:")
        print("   sudo apt install unzip && wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-stable-linux-arm.zip")
        print("   unzip ngrok-stable-linux-arm.zip && sudo mv ngrok /usr/local/bin")

def send_domain_to_laptop(domain):
    """Send the tunnel URL to any reachable laptop host."""
    for host in LAPTOP_HOSTS:
        try:
            url = f"http://{host}:3000/update-domain"
            print(f"📡 Sending Tunnel URL to {url}")
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
