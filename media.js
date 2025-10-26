import express from "express";
import { spawn } from "child_process";
import fs from "fs";
import path from "path";
import fetch from "node-fetch";

const app = express();
const PORT = 3000;

let RPI_FEED_URL = "";

async function detectPi() {
  console.log("🔍 Searching for Raspberry Pi...");

  try {
    // Try local hostname first
    const res = await fetch("http://raspberrypi.local:5000/pi_info.txt", { timeout: 3000 });
    if (!res.ok) throw new Error("Response not OK");
    const text = await res.text();
    RPI_FEED_URL = text.trim();
    console.log(`✅ Raspberry Pi found: ${RPI_FEED_URL}`);
  } catch (err) {
    console.log("❌ No connection to Raspberry Pi.");
    RPI_FEED_URL = "";
  }
}

function startCloudflare() {
  console.log("🌩️ Starting Cloudflare Tunnel...");
  const cfPath = `"C:\\Program Files\\Cloudflared\\cloudflared.exe"`;
  const tunnel = spawn(cfPath, ["tunnel", "--url", `http://localhost:${PORT}`], { shell: true });

  const handleOutput = (data) => {
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
  tunnel.on("exit", (code) => console.log(`⚠️ Cloudflared exited with code ${code}`));
}

app.get("/", (req, res) => {
  if (!RPI_FEED_URL) return res.send("<h1 style='color:red'>❌ No connection to Raspberry Pi</h1>");
  res.send(`<h1>🎥 Raspberry Pi Live Feed</h1>
            <img src="${RPI_FEED_URL}/video_feed" style="width:100%;max-width:640px;">`);
});

app.listen(PORT, async () => {
  console.log(`✅ media.js server running on http://localhost:${PORT}`);
  await detectPi();
  startCloudflare();
});
