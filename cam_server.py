from flask import Flask, Response, jsonify
import cv2, socket, os, subprocess

app = Flask(__name__)

# 🎥 Initialize the webcam (index 0)
camera = cv2.VideoCapture(0)

def get_pi_info():
    """Return hostname and IP address"""
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return hostname, ip
    except Exception as e:
        print("⚠️ IP lookup failed:", e)
        return "raspberrypi", "127.0.0.1"

def generate_frames():
    """Generate MJPEG frames for the stream"""
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

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    hostname, ip = get_pi_info()
    return jsonify({
        "status": "ok",
        "hostname": hostname,
        "ip": ip,
        "message": "Raspberry Pi camera is running"
    })

@app.route('/pi_info.txt')
def pi_info():
    """For media.js auto-detection"""
    hostname, ip = get_pi_info()
    return f"http://{ip}:5000", 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    print("🚀 Raspberry Pi Camera Server starting…")
    print("📡 Access via http://<pi_ip>:5000/video_feed")
    app.run(host='0.0.0.0', port=5000, threaded=True)
