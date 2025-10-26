import http from "http";
import https from "https";
import express from "express";
import { spawn } from "child_process";
import fs from "fs";

const app = express();
const PORT = 3000;

// --- STEP 1: Auto-detect Raspberry Pi IP ---
let RPI_FEED_URL = "";
const raspiDomain = "http://raspberrypi.local:5000";

function detectPi() {
  console.log("🔍 Checking Raspberry Pi...");
  const client = raspiDomain.startsWith("https") ? https : http;

  client
    .get(`${raspiDomain}/pi_info.txt`, res => {
      let data = "";
      res.on("data", chunk => (data += chunk));
      res.on("end", () => {
        RPI_FEED_URL = data.trim();
        console.log(`✅ Raspberry Pi URL detected: ${RPI_FEED_URL}`);
      });
    })
    .on("error", err => {
      console.log("⚠️ No connection to Raspberry Pi");
      RPI_FEED_URL = "";
    });
}

// --- STEP 2: Serve frontend ---
app.get("/", (req, res) => {
  if (!RPI_FEED_URL) return res.send("<h2>No connection to Raspberry Pi</h2>");
  res.send(`
    <html><body style="background:black; margin:0; display:flex; justify-content:center; align-items:center; height:100vh;">
      <img src="${RPI_FEED_URL}/video_feed" style="width:90%; border-radius:10px;"/>
    </body></html>
  `);
});

// --- STEP 3: Start Cloudflare tunnel automatically ---
function startCloudflare() {
  console.log("🌩️ Starting Cloudflare Tunnel...");
  const cfPath = `"C:\\Program Files\\Cloudflared\\cloudflared.exe"`;
  const tunnel = spawn(cfPath, ["tunnel", "--url", `http://localhost:${PORT}`], { shell: true });

  const handleOutput = data => {
    const text = data.toString();
    const match = text.match(/https:\/\/[^\s]+trycloudflare\.com/);
    if (match) {
      const domain = match[0].trim();
      console.log(`\n🌍 Your Cloudflare Tunnel URL: \x1b[36m${domain}\x1b[0m\n`);
      fs.writeFileSync("cloudflare_url.txt", domain);
    }
  };

  tunnel.stdout.on("data", handleOutput);
  tunnel.stderr.on("data", handleOutput);

  tunnel.on("exit", code => {
    console.log(`⚠️ Cloudflared exited with code ${code}`);
  });
}

// --- Start server ---
app.listen(PORT, () => {
  console.log(`✅ media.js server running on http://localhost:${PORT}`);
  detectPi();
  startCloudflare();
});
