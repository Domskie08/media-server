import express from "express";
import axios from "axios";
import os from "os";
import { exec } from "child_process";
import http from "http";
import https from "https";

const app = express();
const PORT = 3000;

const sources = [
  "http://raspberrypi.local:5000/video_feed",
  "http://192.168.137.2:5000/video_feed",
  "http://10.191.254.133:5000/video_feed",
  "http://172.27.44.149:5000/video_feed",
];

let currentStreamURL = null;
let tunnelType = "Cloudflare";
let publicURL = "Waiting...";
let piStatus = "Checking...";

const clients = [];

// --- Helpers ---
function getLocalIPs() {
  const nets = os.networkInterfaces();
  const results = [];
  for (const name of Object.keys(nets)) {
    for (const net of nets[name]) {
      if (net.family === "IPv4" && !net.internal) results.push(net.address);
    }
  }
  return results;
}

async function checkPiStream() {
  for (const url of sources) {
    try {
      await axios.get(url.replace("/video_feed", "/ping"), { timeout: 1500 });
      piStatus = `✅ Connected: ${url}`;
      currentStreamURL = url;
      return url;
    } catch {}
  }
  piStatus = "⚠️ Pi not found";
  currentStreamURL = null;
  return null;
}

// --- Routes ---
app.get("/status", (req, res) => {
  res.json({
    localIPs: getLocalIPs(),
    tunnel: tunnelType,
    publicURL,
    piStatus,
    viewers: clients.length,
  });
});

// MJPEG proxy with multiple viewers
app.get("/video", async (req, res) => {
  if (!currentStreamURL) await checkPiStream();
  if (!currentStreamURL) return res.status(404).send("No Pi stream found");

  clients.push(res);
  res.writeHead(200, {
    "Content-Type": "multipart/x-mixed-replace; boundary=frame",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
  });

  req.on("close", () => {
    const idx = clients.indexOf(res);
    if (idx !== -1) clients.splice(idx, 1);
  });
});

// --- Stream fan-out ---
async function startFanOut() {
  if (!currentStreamURL) return;
  const protocol = currentStreamURL.startsWith("https") ? https : http;
  protocol.get(currentStreamURL, (streamRes) => {
    streamRes.on("data", (chunk) => {
      clients.forEach((client) => {
        try {
          client.write(chunk);
        } catch {}
      });
    });
  }).on("error", (err) => {
    console.error("Fan-out stream error:", err.message);
  });
}

// --- Dashboard ---
app.get("/", (req, res) => {
  res.send(`
<html>
<head><title>Media Server</title></head>
<body>
<h1>📡 Media Server Dashboard</h1>
<p>Pi Status: ${piStatus}</p>
<p>Tunnel: ${tunnelType}</p>
<p>Public URL: ${publicURL}</p>
<p>Viewers: <span id="viewers">0</span></p>
<iframe src="/video" width="640" height="480"></iframe>
<script>
  setInterval(async () => {
    const data = await fetch('/status').then(r => r.json());
    document.getElementById('viewers').innerText = data.viewers;
  }, 2000);
</script>
</body>
</html>
  `);
});

// --- Start Server ---
app.listen(PORT, async () => {
  console.log(`Media server running at http://localhost:${PORT}`);

  await checkPiStream();
  setInterval(checkPiStream, 5000);
  setInterval(startFanOut, 1000);

  const ips = getLocalIPs();
  console.log("Local IPs:", ips.join(", "));

  // --- Cloudflare Tunnel Start ---
  const cloudProc = exec(`cloudflared tunnel --url http://localhost:${PORT} --loglevel info`);
  const detectURL = (text) => {
    const match = text.match(/https:\/\/[a-z0-9.-]+\.trycloudflare\.com/);
    if (match) {
      publicURL = match[0];
      console.log("🌐 Cloudflare Public URL:", publicURL);
    }
  };
  cloudProc.stdout.on("data", (data) => detectURL(data.toString()));
  cloudProc.stderr.on("data", (data) => detectURL(data.toString()));
});
