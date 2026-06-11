// Verify the real-data heatmap fixes: historical field, walls, price trace, sync.
const path = require("node:path");
const gp = path.join(process.env.APPDATA || "", "npm/node_modules/playwright-core");
const { chromium } = require(gp);
const EXE = process.env.CHROME_EXE;

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, headless: true });
  const page = await browser.newPage({ viewport: { width: 1366, height: 800 } });
  const errs = [];
  page.on("pageerror", (e) => errs.push(e.message.slice(0, 160)));
  page.on("console", (m) => { if (m.type() === "error") errs.push(m.text().slice(0, 160)); });

  await page.goto("http://localhost:3000/preview/real", { waitUntil: "networkidle" });
  await page.waitForTimeout(2800);

  const info = await page.evaluate(() => {
    const body = document.body.innerText;
    // overlay level tags: look for C1/C2/C3 (call walls), P1.. (put walls), FLIP
    const tags = [...document.querySelectorAll("svg + *, .font-mono")].map(e => e.textContent).filter(Boolean);
    const hasC = /\bC1\b/.test(body);
    const hasP = /\bP1\b/.test(body);
    const hasFlip = /FLIP/.test(body);
    // price trace svg path present?
    const paths = [...document.querySelectorAll("svg path")].map(p => (p.getAttribute("d")||"").slice(0,4));
    const tracePath = paths.find(d => d.startsWith("M "));
    const range = document.querySelector("input[type='range']");
    const regime = document.querySelector("[aria-label^='Regime']");
    return {
      frameIdx: range ? Number(range.value) : null,
      regime: regime ? regime.getAttribute("aria-label") : null,
      hasCallWallTag: hasC, hasPutWallTag: hasP, hasFlip,
      svgPathCount: paths.length,
      hasTracePath: !!tracePath,
    };
  });

  await page.locator("canvas").first().screenshot({ path: "C:/tmp/fix_canvas.png" });
  // full chart area (profile + axis + heatmap) for sync inspection
  await page.screenshot({ path: "C:/tmp/fix_full.png", clip: { x: 0, y: 90, width: 1366, height: 640 } });

  console.log(JSON.stringify(info));
  console.log("ERRORS:", errs.length ? JSON.stringify(errs) : "none");
  await browser.close();
})().catch((e) => { console.error("FAIL:", e.message); process.exit(1); });
