// Screenshot the viewer from multiple angles / modes.
import { chromium } from "playwright";

const browser = await chromium.launch({ args: ["--use-gl=angle", "--enable-webgl", "--ignore-gpu-blocklist"] });
const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
page.on("console", (m) => { if (m.type() === "error") console.log("PAGE ERROR:", m.text()); });
page.on("pageerror", (e) => console.log("PAGE EXCEPTION:", e.message));

await page.goto("http://localhost:8742/viewer/index.html");
await page.waitForTimeout(2500);
await page.screenshot({ path: "plans/crops/shot_orbit.png" });

// custom camera positions via exposed API if available; otherwise keyboard/mouse
const views = JSON.parse(process.argv[2] || "[]");
for (let i = 0; i < views.length; i++) {
  const v = views[i];
  await page.evaluate((v) => window.__setCam && window.__setCam(v), v);
  await page.waitForTimeout(400);
  await page.screenshot({ path: `plans/crops/shot_${v.name || i}.png` });
}
await browser.close();
console.log("done");
