from flask import Flask, Response
import cv2, socket, os
import logging

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

@app.route("/ping")
def ping():
    return "pong"

def gen_frames():
    while True:
        success, frame = camera.read()
        if not success:
            continue
        ret, buffer = cv2.imencode(".jpg", frame)
        frame = buffer.tobytes()
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")

@app.route("/video_feed")
def video_feed():
    return Response(gen_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

def print_ips():
    os.system("hostname -I > /tmp/iplist.txt")
    with open("/tmp/iplist.txt") as f:
        ips = f.read().strip().split()
    print("✅ Raspberry Pi IPs:", ips)
    return ips

if __name__ == "__main__":
    print_ips()
    hostname = socket.gethostname()
    print(f"✅ Hostname: {hostname}.local")
    app.run(host="0.0.0.0", port=5000)
