import express from "express";
import fs from "fs";

const app = express();
const PORT = 3000;

app.use(express.json());

let RPI_FEED_URL = null;

// ✅ Auto-update from Raspberry Pi
app.post("/update-domain", (req, res) => {
  const { url } = req.body;
  if (url) {
    // 🔄 H.264 stream via HLS
    RPI_FEED_URL = `${url}/hls/index.m3u8`;
    fs.writeFileSync("rpi_domain.txt", RPI_FEED_URL);
    console.log(`🔁 Updated Raspberry Pi H.264/HLS domain: ${RPI_FEED_URL}`);
    res.sendStatus(200);
  } else {
    res.sendStatus(400);
  }
});

// ✅ Main page with HLS video
app.get("/", (req, res) => {
  if (!RPI_FEED_URL) {
    RPI_FEED_URL = fs.existsSync("rpi_domain.txt")
      ? fs.readFileSync("rpi_domain.txt", "utf-8")
      : "No connection to Raspberry Pi";
  }

  const isConnected = RPI_FEED_URL.includes("http");

  res.send(`
    <html>
      <head>
        <title>Raspberry Pi H.264 Stream</title>
        <script src="https://cdn.jsdelivr.net/npm/hls.js@1.4.0"></script>
        <style>
          body {
            background:black;
            display:flex;
            align-items:center;
            justify-content:center;
            height:100vh;
            margin:0;
          }
          video {
            width:100%;
            max-width:800px;
            height:auto;
            border-radius:12px;
            box-shadow:0 0 20px rgba(255,255,255,0.3);
          }
          h2 { color:white; font-family:sans-serif; }
        </style>
      </head>
      <body>
        ${
          isConnected
            ? `<video id="stream" controls autoplay muted playsinline></video>`
            : `<h2>No connection to Raspberry Pi</h2>`
        }
        <script>
          const video = document.getElementById('stream');
          const streamUrl = "${RPI_FEED_URL}";

          if (Hls.isSupported() && streamUrl) {
            const hls = new Hls();
            hls.loadSource(streamUrl);
            hls.attachMedia(video);
            hls.on(Hls.Events.MANIFEST_PARSED, function() {
              video.play();
            });
          } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
            video.src = streamUrl;
            video.addEventListener('loadedmetadata', function() {
              video.play();
            });
          }
        </script>
      </body>
    </html>
  `);
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`✅ media.js server running on http://0.0.0.0:${PORT}`);
});
