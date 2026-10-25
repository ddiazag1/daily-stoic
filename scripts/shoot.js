// Screenshot the app at iPhone width in light and dark mode.
// usage: node scripts/shoot.js <url-hash> <outprefix>
const path = require("path");
const fs = require("fs");
const pw = require(process.env.PW_CORE || "C:/Users/Daniel/.openclaw/workspace/soldotna-homes/node_modules/playwright-core");

const CHROME = ["C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"].find((p) => fs.existsSync(p));

(async () => {
  const hash = process.argv[2] || "#/";
  const out = process.argv[3] || "shots/today";
  const full = process.argv[4] === "full";
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const browser = await pw.chromium.launch({ executablePath: CHROME, headless: true });
  for (const scheme of ["light", "dark"]) {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true,
      colorScheme: scheme, reducedMotion: "reduce",
      userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    });
    const page = await ctx.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    await page.goto(`http://127.0.0.1:8765/${hash}`, { waitUntil: "networkidle" });
    await page.waitForSelector("h1");
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${out}-${scheme}.png`, fullPage: full });
    console.log(`${out}-${scheme}.png`, errors.length ? `ERRORS: ${errors.join(" | ")}` : "no console errors");
    await ctx.close();
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
