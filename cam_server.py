from flask import Flask, Response, jsonify
import cv2

app = Flask(__name__)

# ✅ Try to open the USB webcam
camera = cv2.VideoCapture(0)  # use 1 if you have multiple cameras

def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            print("⚠️ No camera feed detected.")
            break
        else:
            # Encode frame to JPEG for streaming
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
    # Simple endpoint for the laptop to check if Pi is online
    return jsonify({"status": "ok", "message": "Raspberry Pi camera is running"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
