import express from "express";
import fs from "fs";

const app = express();
const PORT = 3000;

app.use(express.json());

let RPI_FEED_URL = null;

// ✅ Receive HLS URL from Pi
app.post("/update-domain", (req, res) => {
  const { url } = req.body;
  if (url) {
    RPI_FEED_URL = url;
    fs.writeFileSync("rpi_domain.txt", RPI_FEED_URL);
    console.log(`🔁 Updated HLS URL: ${RPI_FEED_URL}`);
    res.sendStatus(200);
  } else {
    res.sendStatus(400);
  }
});

// ✅ Serve HTML page with HLS.js player
app.get("/", (req, res) => {
  if (!RPI_FEED_URL) {
    RPI_FEED_URL = fs.existsSync("rpi_domain.txt") ? fs.readFileSync("rpi_domain.txt", "utf-8") : null;
  }

  if (!RPI_FEED_URL) {
    res.send("<h2>No connection to Raspberry Pi</h2>");
    return;
  }

  res.send(`
    <html>
      <head>
        <title>Raspberry Pi H.264 HLS Stream</title>
        <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
      </head>
      <body style="margin:0;background:black;display:flex;justify-content:center;align-items:center;height:100vh;">
        <video id="video" controls autoplay playsinline muted style="width:100%;height:auto;"></video>
        <script>
          const video = document.getElementById('video');
          const url = "${RPI_FEED_URL}";
          if(Hls.isSupported()) {
            const hls = new Hls();
            hls.loadSource(url);
            hls.attachMedia(video);
            hls.on(Hls.Events.MANIFEST_PARSED, () => video.play());
          } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
            video.src = url;
            video.addEventListener('loadedmetadata', () => video.play());
          }
        </script>
      </body>
    </html>
  `);
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`✅ Media server running on http://0.0.0.0:${PORT}`);
});
