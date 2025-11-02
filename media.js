import express from "express";
import axios from "axios";
import os from "os";
import { exec } from "child_process";
import http from "http";

const app = express();
const PORT = 3000;

// Candidate Pi URLs
const sources = [
  "http://raspberrypi.local:5000/video_feed",
  "http://192.168.137.2:5000/video_feed",
  "http://10.191.254.91:5000/video_feed",
  "http://172.27.44.2:5000/video_feed",
];

let tunnelType = "None";
let publicURL = "Waiting...";
let piStatus = "Checking...";
let currentStreamURL = null;
let activeStudent = null; // track current connected student

// Get local IPs
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

// Check Pi availability
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

// Dashboard JSON status
app.get("/status", (req, res) => {
  res.json({
    localIPs: getLocalIPs(),
    tunnel: tunnelType,
    publicURL,
    piStatus,
    activeStudent: activeStudent ? "Occupied" : "Available",
  });
});

// Single-student MJPEG proxy
app.get("/video", async (req, res) => {
  const studentIP = req.ip;
  
  if (!currentStreamURL) await checkPiStream();
  if (!currentStreamURL) return res.status(404).send("No Raspberry Pi stream found.");

  // Only one student at a time
  if (activeStudent && activeStudent !== studentIP) {
    return res.status(403).send("🚫 Stream is currently in use by another student.");
  }
  activeStudent = studentIP;

  res.writeHead(200, {
    "Content-Type": "multipart/x-mixed-replace; boundary=frame",
    "Cache-Control": "no-cache",
    "Connection": "close"
  });

  const streamReq = http.get(currentStreamURL, (streamRes) => {
    streamRes.on("data", (chunk) => res.write(chunk));
    // Do not end response
  });

  streamReq.on("error", (err) => {
    console.error("Stream error:", err.message);
    res.end();
    activeStudent = null;
  });

  req.on("close", () => {
    streamReq.abort();
    activeStudent = null;
  });
});

// Dashboard HTML
app.get("/", (req, res) => {
  res.send(`
    <html>
    <head>
      <title>📡 Media Server Dashboard</title>
      <style>
        body { font-family: Arial; background: #121212; color: #eee; text-align: center; padding: 40px; }
        .card { background: #1e1e1e; padding: 25px; border-radius: 15px; display: inline-block; min-width: 420px; box-shadow: 0 0 15px rgba(0,0,0,0.5); }
        h1 { color: #00c3ff; }
        button { padding: 10px 20px; border: none; border-radius: 10px; background: #00c3ff; color: white; cursor: pointer; }
        button:hover { background: #009ed8; }
        iframe { margin-top: 20px; border-radius: 10px; width: 640px; height: 480px; border: none; background: black; }
        .info { text-align: left; margin-top: 20px; }
      </style>
    </head>
    <body>
      <div class="card">
        <h1>🎥 Media Server Dashboard</h1>
        <div id="content"><p>Loading...</p></div>
        <iframe id="videoFrame" src="" allowfullscreen></iframe><br>
        <button onclick="reconnect()">🔁 Reconnect Pi</button>
      </div>

      <script>
        async function loadStatus() {
          try {
            const res = await fetch('/status');
            const data = await res.json();
            let html = "<div class='info'>";
            html += "<b>Local IPs:</b><br>" + data.localIPs.join(", ") + "<br><br>";
            html += "<b>Raspberry Pi:</b> " + data.piStatus + "<br><br>";
            html += "<b>Tunnel Type:</b> " + data.tunnel + "<br><br>";
            html += "<b>Public URL:</b> <span id='url'>" + data.publicURL + "</span><br><br>";
            html += "<b>Stream Status:</b> " + (data.activeStudent || "Available") + "<br><br>";
            if (data.publicURL.startsWith("http")) html += "<button onclick='copyLink()'>Copy Link</button>";
            html += "</div>";
            document.getElementById('content').innerHTML = html;

            if (data.piStatus.startsWith("✅") && !data.activeStudent) {
              document.getElementById('videoFrame').src = "/video";
            } else if (data.activeStudent === "Occupied") {
              document.getElementById('videoFrame').src = "";
            }
          } catch (err) { console.error(err); }
        }

        function copyLink() {
          navigator.clipboard.writeText(document.getElementById('url').innerText);
          alert("Copied!");
        }

        async function reconnect() {
          await fetch('/status');
          document.getElementById('videoFrame').src = "/video";
        }

        loadStatus();
        setInterval(loadStatus, 3000);
      </script>
    </body>
    </html>
  `);
});

// Start server and launch tunnel
app.listen(PORT, async () => {
  console.log(`💻 Media server running at http://localhost:${PORT}`);
  const ips = getLocalIPs();
  console.log("🖥️ Local IPs:", ips.join(","));

  setInterval(checkPiStream, 5000);
  await checkPiStream();

  if (ips.some(ip => ip.startsWith("172.27.44"))) {
    console.log("🏢 Office network detected (172.27.44.*)");
    tunnelType = "Ngrok";
    const ngrokProc = exec(`ngrok http ${PORT}`);
    ngrokProc.stdout.on("data", data => {
      const match = data.match(/https:\/\/[a-z0-9.-]+\.ngrok\.io/);
      if (match) publicURL = match[0];
    });
  } else {
    console.log("🏠 Home/Hotspot network detected");
    tunnelType = "Cloudflare";
    const cloudProc = exec(`cloudflared tunnel --url http://localhost:${PORT}`);
    const detectURL = text => {
      const match = text.match(/https:\/\/[a-z0-9.-]+\.trycloudflare\.com/);
      if (match) publicURL = match[0];
    };
    cloudProc.stdout.on("data", data => detectURL(data.toString()));
    cloudProc.stderr.on("data", data => detectURL(data.toString()));
  }
});
