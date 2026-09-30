const puppeteer = require("puppeteer-core");
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const framesDir = path.join(__dirname, "frames");
if (fs.existsSync(framesDir)) {
  fs.rmSync(framesDir, { recursive: true, force: true });
}
fs.mkdirSync(framesDir, { recursive: true });

let frameCount = 0;
const fps = 8;
const frameInterval = 1000 / fps;

async function recordFrames(page, durationMs) {
  const steps = Math.floor(durationMs / frameInterval);
  for (let i = 0; i < steps; i++) {
    frameCount++;
    const framePath = path.join(
      framesDir,
      `frame_${String(frameCount).padStart(5, "0")}.png`
    );
    await page.screenshot({ path: framePath, type: "png" });
    await new Promise((r) => setTimeout(r, frameInterval));
  }
}

async function typeText(page, selector, text) {
  for (const char of text) {
    await page.type(selector, char, { delay: 40 });
    frameCount++;
    const framePath = path.join(
      framesDir,
      `frame_${String(frameCount).padStart(5, "0")}.png`
    );
    await page.screenshot({ path: framePath, type: "png" });
  }
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "/usr/bin/google-chrome",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--headless=new"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800, deviceScaleFactor: 1 });

  console.log("Navigating to Travel Concierge web app...");
  await page.goto("https://travel-concierge-frontend-406128335446.us-east1.run.app", {
    waitUntil: "networkidle2",
  });

  // Hold initial view
  console.log("Recording initial view...");
  await recordFrames(page, 2000);

  // Prompt 1: First prompt showing what app does best
  const prompt1 = "Find top beach destinations in Mexico";
  console.log(`Typing prompt 1: "${prompt1}"`);
  await typeText(page, "#input", prompt1);
  await recordFrames(page, 500);

  console.log("Submitting prompt 1...");
  await page.click("button");
  
  // Wait for response bubble to appear
  await page.waitForSelector(".msg.agent", { timeout: 35000 });
  console.log("Agent responded to prompt 1!");
  await recordFrames(page, 4000);

  // Prompt 2: Richer prompt showing tool call / live weather / image
  const prompt2 = "What is the weather forecast for Tokyo and generate a photo of a Tokyo temple?";
  console.log(`Typing prompt 2: "${prompt2}"`);
  await typeText(page, "#input", prompt2);
  await recordFrames(page, 500);

  console.log("Submitting prompt 2...");
  await page.click("button");

  // Wait for second agent response
  await page.waitForFunction(
    () => document.querySelectorAll(".msg.agent").length >= 2,
    { timeout: 45000 }
  );
  console.log("Agent responded to prompt 2!");
  await recordFrames(page, 5000);

  await browser.close();
  console.log(`Recorded ${frameCount} frames.`);

  // Convert frames to mp4 using ffmpeg
  const outputMp4 = path.join(__dirname, "travel_concierge_demo.mp4");
  console.log("Compiling MP4 video with ffmpeg...");
  execSync(
    `ffmpeg -y -framerate ${fps} -i "${framesDir}/frame_%05d.png" -c:v libx264 -pix_fmt yuv420p "${outputMp4}"`
  );
  console.log(`Successfully created demo video: ${outputMp4}`);
})();
