import express from "express";
import path from "path";
import { fileURLToPath } from "url";
import bodyParser from "body-parser";
import fs from "fs";

const app = express();
const PORT = 3000;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

app.use(bodyParser.json());
app.use(express.static(path.join(__dirname, "public")));

let currentDomain = "";

// ------------------------------------------------------
// 📡 API Endpoint - update from Raspberry Pi
// ------------------------------------------------------
app.post("/update-domain", (req, res) => {
  const { url } = req.body;
  if (!url) return res.status(400).json({ error: "Missing URL" });

  currentDomain = url;
  console.log(`✅ Received RTSP tunnel URL: ${url}`);

  // Save for persistence (optional)
  fs.writeFileSync("domain.txt", url);

  res.json({ message: "Domain updated", url });
});

// ------------------------------------------------------
// 🌐 Frontend page - show video player
// ------------------------------------------------------
app.get("/", (req, res) => {
  res.send(`
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>RTSP Live Stream</title>
<style>
  body {
    margin: 0; padding: 0;
    background: #111; color: #fff;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    height: 100vh;
    font-family: sans-serif;
  }
  video {
    width: 80%; max-width: 900px;
    border: 3px solid #00ffcc;
    border-radius: 16px;
    box-shadow: 0 0 20px #00ffaa88;
    background: black;
  }
  #domain {
    margin-top: 20px;
    font-size: 1.1em;
    color: #0f0;
  }
</style>
</head>
<body>
  <h2>🎥 RTSP Live Stream</h2>
  <video id="videoPlayer" controls autoplay muted playsinline></video>
  <div id="domain">Waiting for stream URL...</div>

  <script src="https://cdn.jsdelivr.net/npm/jsmpeg@0.2.1/jsmpeg.min.js"></script>
  <script>
    async function loadStream() {
      const res = await fetch('/current-domain');
      const data = await res.json();
      const url = data.url;

      document.getElementById('domain').innerText = url ? url : 'No stream yet';

      if (!url) return;

      // If it's RTSP, show hint to use VLC
      if (url.startsWith('rtsp://')) {
        document.getElementById('domain').innerHTML = 
          "📡 RTSP Stream available: <br><b>" + url + "</b><br><br>" +
          "Use <b>VLC</b> or <b>OBS</b> to watch directly.";
      } else {
        // Cloudflare or Ngrok HTTPS
        document.getElementById('domain').innerHTML = 
          "🌍 Tunnel active: <b>" + url + "</b>";
      }
    }

    setInterval(loadStream, 5000);
    loadStream();
  </script>
</body>
</html>
  `);
});

// ------------------------------------------------------
// 🧠 Return current domain for frontend
// ------------------------------------------------------
app.get("/current-domain", (req, res) => {
  res.json({ url: currentDomain });
});

// ------------------------------------------------------
app.listen(PORT, "0.0.0.0", () =>
  console.log(`✅ Media server running on http://0.0.0.0:${PORT}`)
);
