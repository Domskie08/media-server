import subprocess
import requests
import time
import re
import os

# 🧠 CONFIG — edit this to your setup
PORT = 5000  # Your video feed port (Flask or similar)
LAPTOP_SERVER = "http://192.168.1.105:3000/update-domain"  # Replace with your laptop's LAN IP
CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"  # Adjust if in different path
HOME_DIR = os.path.expanduser("~")

# 🧩 Start your Flask camera stream in background
print("🎥 Starting video feed...")
stream_process = subprocess.Popen(["python3", "camera.py"])  # change to your video script name
time.sleep(5)

# 🌀 Start Cloudflare tunnel
print("☁️  Starting Cloudflare tunnel...")
process = subprocess.Popen(
    [CLOUDFLARED_PATH, "tunnel", "--no-autoupdate", "--protocol", "http2", "--url", f"http://localhost:{PORT}"],
    cwd=HOME_DIR,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

# 🕵️ Read output until we find the public URL
public_url = None
for line in process.stdout:
    print(line.strip())
    match = re.search(r"https://[-a-zA-Z0-9]+\.trycloudflare\.com", line)
    if match:
        public_url = match.group(0)
        print(f"🌍 Tunnel URL detected: {public_url}")
        break

# 🔗 Send the Cloudflare domain to your Node.js server
if public_url:
    try:
        print(f"📡 Sending Cloudflare URL to {LAPTOP_SERVER} ...")
        response = requests.post(LAPTOP_SERVER, json={"url": public_url})
        if response.status_code == 200:
            print("✅ Successfully sent to laptop server!")
        else:
            print(f"⚠️ Server responded with status {response.status_code}")
    except Exception as e:
        print(f"❌ Error sending URL: {e}")
else:
    print("🚫 No Cloudflare URL detected. Check cloudflared logs.")

# Keep process alive
process.wait()
