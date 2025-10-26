from flask import Flask, Response, jsonify
import cv2
import socket

app = Flask(__name__)

# ✅ Try to open the USB camera (0 = first camera)
camera = cv2.VideoCapture(0)

# --- Helper: Get Raspberry Pi info (hostname + IP) ---
def get_pi_info():
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return hostname, ip
    except Exception as e:
        print("⚠️ Failed to get IP:", e)
        return "raspberrypi", "127.0.0.1"

# --- Generate MJPEG frames for streaming ---
def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            print("⚠️ No camera feed detected.")
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# --- Main video feed route ---
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# --- Status route (for health check) ---
@app.route('/status')
def status():
    hostname, ip = get_pi_info()
    return jsonify({
        "status": "ok",
        "hostname": hostname,
        "ip": ip,
        "message": "Raspberry Pi camera is running"
    })

# --- Pi Info route (for media.js auto detection) ---
@app.route('/pi_info.txt')
def pi_info_file():
    hostname, ip = get_pi_info()
    return f"http://{ip}:5000", 200, {'Content-Type': 'text/plain'}

# --- Start the Flask app ---
if __name__ == '__main__':
    print("🚀 Raspberry Pi Camera Server starting...")
    print("🟢 Access via http://<pi_ip>:5000/video_feed")
    print("🧠 or http://raspberrypi.local:5000/video_feed (if hostname works)")
    app.run(host='0.0.0.0', port=5000, threaded=True)
