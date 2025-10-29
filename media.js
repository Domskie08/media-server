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
    // ✅ H.264 (HLS) video
    RPI_FEED_URL = `${url}/hls/index.m3u8`;
    fs.writeFileSync("rpi_domain.txt", RPI_FEED_URL);
    console.log(`🔁 Updated Raspberry Pi HLS domain: ${RPI_FEED_URL}`);
    res.sendStatus(200);
  } else {
    res.sendStatus(400);
  }
});

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
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
        <style>
          body {
            background: black;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
            flex-direction: column;
          }
          video {
            width: 90%;
            max-width: 900px;
            border-radius: 12px;
            box-shadow: 0 0 25px rgba(255,255,255,0.2);
          }
          h2 { color: white; font-family: sans-serif; }
        </style>
      </head>
      <body>
        ${
          isConnected
            ? `
            <video id="stream" controls autoplay playsinline muted></video>
            <script>
              const video = document.getElementById('stream');
              const videoSrc = '${RPI_FEED_URL}';
              if (Hls.isSupported()) {
                const hls = new Hls();
                hls.loadSource(videoSrc);
                hls.attachMedia(video);
              } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                video.src = videoSrc;
              }
            </script>`
            : `<h2>No connection to Raspberry Pi</h2>`
        }
      </body>
    </html>
  `);
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`✅ media.js server running on http://0.0.0.0:${PORT}`);
});
