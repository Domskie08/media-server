from flask import Flask, Response
import cv2
import threading
import subprocess
import re
import os

app = Flask(__name__)
camera = cv2.VideoCapture(0)  # change index if needed

def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            _, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

def start_cloudflare():
    print("🌩️ Starting Cloudflare Tunnel...")
    cmd = ["cloudflared", "tunnel", "--url", "http://localhost:5000"]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    for line in process.stdout:
        print(line.strip())
        match = re.search(r"https:\/\/[^\s]+trycloudflare\.com", line)
        if match:
            domain = match.group(0)
            print(f"\n🌍 Raspberry Pi Cloudflare URL: {domain}\n")
            with open("cloudflare_url.txt", "w") as f:
                f.write(domain)
            break

threading.Thread(target=start_cloudflare, daemon=True).start()

if __name__ == '__main__':
    from waitress import serve
    print("✅ Starting Raspberry Pi Camera Server on http://localhost:5000")
    serve(app, host='0.0.0.0', port=5000)
    
#curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb -o cloudflared.deb
#sudo apt install ./cloudflared.deb -y