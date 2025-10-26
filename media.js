import express from "express";
import { spawn } from "child_process";
import fs from "fs";

const app = express();
const PORT = 3000;
let RPI_URL = "http://raspberrypi.local:5000/video_feed"; // default value

if (fs.existsSync("cloudflare_url.txt")) {
  const raspiDomain = fs.readFileSync("cloudflare_url.txt", "utf8").trim();
  if (raspiDomain.startsWith("https://")) {
    RPI_URL = `${raspiDomain}/video_feed`;
  }
}

app.get("/", (req, res) => {
  res.send(`
    <h1>✅ Media Server Running</h1>
    <p>📡 Watching feed from: ${RPI_URL}</p>
  `);
});

app.listen(PORT, () => {
  console.log(`✅ media.js server running on http://localhost:${PORT}`);
  console.log(`📡 Watching feed from: ${RPI_URL}`);
  startCloudflare();
});

function startCloudflare() {
  console.log("🌩️ Starting Cloudflare Tunnel...");

  const cfPath = `"C:\\Program Files\\Cloudflared\\cloudflared.exe"`;
  const tunnel = spawn(cfPath, ["tunnel", "--url", `http://localhost:${PORT}`], { shell: true });

  // ✅ Common function to detect and show URL
  const handleOutput = (data) => {
    const text = data.toString();
    const match = text.match(/https:\/\/[^\s]+trycloudflare\.com/);

    if (match) {
      const domain = match[0].trim();
      console.log(`\n🌍 Your Cloudflare Tunnel URL: \x1b[36m${domain}\x1b[0m\n`);
      fs.writeFileSync("cloudflare_url.txt", domain);
    }
  };

  // 🔍 Listen to both output channels
  tunnel.stdout.on("data", handleOutput);
  tunnel.stderr.on("data", handleOutput);

  tunnel.on("exit", (code) => {
    console.log(`⚠️ Cloudflared exited with code ${code}`);
  });
}
