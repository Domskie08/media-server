const express = require("express");
const axios = require("axios");
const { exec } = require("child_process");
const os = require("os");

const app = express();
const PORT = 3000;

let tunnelType = "None";
let publicURL = "Not yet available";

// Possible Pi stream URLs
const sources = [
  "http://raspberrypi.local:5000/video_feed",
  "http://192.168.137.2:5000/video_feed",
  "http://10.0.0.8:5000/video_feed",
  "http://172.27.44.2:5000/video_feed"
];

function getLocalIPs() {
  const nets = os.networkInterfaces();
  const results = [];
  for (const name of Object.keys(nets)) {
    for (const net of nets[name]) {
      if (net.family === "IPv4" && !net.internal) {
        results.push(net.address);
      }
    }
  }
  return results;
}

async function findPiStream() {
  for (const url of sources) {
    try {
      await axios.get(url.replace("video_feed", "ping"), { timeout: 800 });
      console.log(`✅ Connected to Raspberry Pi at ${url}`);
      return url;
    } catch {
      console.log(`❌ ${url} not reachable`);
    }
  }
  console.log("⚠️ Raspberry Pi stream not found");
  return null;
}

// API to get status info
app.get("/status", (req, res) => {
  res.json({
    localIPs: getLocalIPs(),
    tunnel: tunnelType,
    publicURL,
  });
});

// Main dashboard
app.get("/", (req, res) => {
  res.send(`
    <html>
    <head>
      <title>Media Server Dashboard</title>
      <style>
        body { font-family: Arial; background: #121212; color: #eee; text-align: center; padding: 40px; }
        .card { background: #1e1e1e; padding: 25px; border-radius: 15px; display: inline-block; min-width: 400px; }
        h1 { color: #00c3ff; }
        button { padding: 10px 20px; border: none; border-radius: 10px; background: #00c3ff; color: white; cursor: pointer; }
        button:hover { background: #009ed8; }
        .info { text-align: left; margin-top: 20px; }
      </style>
    </head>
    <body>
      <div class="card">
        <h1>🎥 Media Server Dashboard</h1>
        <div id="content">
          <p>Loading status...</p>
        </div>
      </div>

      <script>
        async function loadStatus() {
          const res = await fetch('/status');
          const data = await res.json();
          let html = "<div class='info'>";
          html += "<b>Local IPs:</b><br>" + data.localIPs.join(", ") + "<br><br>";
          html += "<b>Tunnel Type:</b> " + data.tunnel + "<br><br>";
          html += "<b>Public URL:</b> <span id='url'>" + data.publicURL + "</span><br><br>";
          if (data.publicURL && data.publicURL.startsWith("http")) {
            html += "<button onclick='copyLink()'>Copy Link</button>";
          }
          html += "</div>";
          document.getElementById('content').innerHTML = html;
        }

        function copyLink() {
          const url = document.getElementById('url').innerText;
          navigator.clipboard.writeText(url);
          alert("Copied: " + url);
        }

        loadStatus();
        setInterval(loadStatus, 3000);
      </script>
    </body>
    </html>
  `);
});

// Video redirect
app.get("/video", async (req, res) => {
  const streamUrl = await findPiStream();
  if (!streamUrl) return res.status(404).send("Pi not found");
  res.redirect(streamUrl);
});

// Start server
app.listen(PORT, async () => {
  console.log(`💻 Media server running at http://localhost:${PORT}`);

  const ips = getLocalIPs();
  console.log("🖥️ Local IPs:", ips.join(", "));

  // Detect network type
  if (ips.some(ip => ip.startsWith("172.27.44"))) {
    console.log("🏢 Office Network detected (172.27.44.*)");
    tunnelType = "Ngrok";
    console.log("🚀 Launching Ngrok...");
    const ngrokProc = exec(`ngrok http ${PORT}`);

    ngrokProc.stdout.on("data", data => {
      const match = data.match(/https:\/\/[a-z0-9.-]+\.ngrok\.io/);
      if (match) {
        publicURL = match[0];
        console.log("🌍 Public URL:", publicURL);
      }
    });

  } else {
    console.log("🏠 Home/Hotspot network detected");
    tunnelType = "Cloudflare";
    console.log("🚀 Launching Cloudflare tunnel...");
    const cloudProc = exec(`cloudflared tunnel --url http://localhost:${PORT}`);

    cloudProc.stdout.on("data", data => {
      const match = data.match(/https:\/\/[-a-z0-9.]+\.trycloudflare\.com/);
      if (match) {
        publicURL = match[0];
        console.log("🌍 Public URL:", publicURL);
      }
    });
  }
});
