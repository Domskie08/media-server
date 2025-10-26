from flask import Flask, Response, jsonify
import cv2, socket

app = Flask(__name__)
camera = cv2.VideoCapture(0)

def get_pi_info():
    """Return hostname and real LAN IP"""
    hostname = socket.gethostname()
    try:
        # Create a dummy socket to get LAN IP instead of 127.x.x.x
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    return hostname, ip

def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            print("⚠️ No camera feed detected.")
            break
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/pi_info.txt')
def pi_info():
    hostname, ip = get_pi_info()
    return f"http://{ip}:5000", 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    print("🚀 Raspberry Pi Camera Server starting…")
    app.run(host='0.0.0.0', port=5000, threaded=True)
