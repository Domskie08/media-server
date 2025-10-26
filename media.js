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

  res.send(`
    <html>
      <body style="background:black;display:flex;align-items:center;justify-content:center;height:100vh;">
        ${RPI_FEED_URL.includes("http")
          ? `<img src="${RPI_FEED_URL}" style="width:100%;height:auto;">`
          : `<h2 style="color:white;">No connection to Raspberry Pi</h2>`}
      </body>
    </html>
  `);
});

app.listen(PORT, () => {
  console.log(`✅ media.js server running on http://localhost:${PORT}`);
});
