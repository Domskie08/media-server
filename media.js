import express from "express";
import fs from "fs";

const app = express();
const PORT = 3000;

app.use(express.json());

let RPI_FEED_URL = null;

app.post("/update-domain", (req, res) => {
  const { url } = req.body;
  if (url) {
    // H.264 stream (direct from Raspberry Pi)
    RPI_FEED_URL = `${url}/video_feed`;
    fs.writeFileSync("rpi_domain.txt", RPI_FEED_URL);
    console.log(`🔁 Updated Raspberry Pi domain: ${RPI_FEED_URL}`);
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
        <style>
          body { background:black; display:flex; align-items:center; justify-content:center; height:100vh; margin:0; }
          video { width:100%; height:auto; border-radius:12px; box-shadow:0 0 20px rgba(255,255,255,0.3); }
          h2 { color:white; font-family:sans-serif; }
        </style>
      </head>
      <body>
        ${
          isConnected
            ? `<video id="stream" controls autoplay playsinline muted>
                <source src="${RPI_FEED_URL}" type="video/mp4">
                Your browser does not support H.264 playback.
               </video>`
            : `<h2>No connection to Raspberry Pi</h2>`
        }
      </body>
    </html>
  `);
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`✅ media.js server running on http://0.0.0.0:${PORT}`);
});
