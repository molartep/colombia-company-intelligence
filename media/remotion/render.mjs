import { bundle } from "@remotion/bundler";
import {
  selectComposition,
  renderMedia,
  renderStill,
  openBrowser,
} from "@remotion/renderer";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
const root = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2),
  still = args.includes("--stills"),
  asset = args.find((x) => ["promo", "walkthrough", "gif"].includes(x));
const browserExecutable =
  process.env.CCI_CHROME ||
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const serveUrl = await bundle({
  entryPoint: path.join(root, "src/index.tsx"),
  publicDir: path.join(root, "public"),
  outDir: path.join(root, "build"),
  onProgress: () => {},
});
const browser = await openBrowser("chrome", { browserExecutable });
const work = path.join(root, "../exports/.work");
fs.mkdirSync(work, { recursive: true });
const review = path.join(root, "../captures/review-v2");
fs.mkdirSync(review, { recursive: true });
const specs = JSON.parse(
  fs.readFileSync(path.join(root, "../src/story.json"), "utf8"),
);
try {
  for (const id of asset ? [asset] : ["promo", "walkthrough", "gif"]) {
    const composition = await selectComposition({
      serveUrl,
      id,
      browserExecutable,
      puppeteerInstance: browser,
    });
    if (still) {
      for (let i = 0; i < specs[id].scenes.length; i++) {
        const s = specs[id].scenes[i],
          seconds = (s.start + s.end) / 2;
        await renderStill({
          serveUrl,
          composition,
          frame: Math.floor(seconds * 60),
          output: path.join(review, `${id}-${i}.png`),
          puppeteerInstance: browser,
          browserExecutable,
          imageFormat: "png",
        });
      }
      for (const seconds of [0, 0.25, 1, 2])
        await renderStill({
          serveUrl,
          composition,
          frame: Math.round(seconds * 60),
          output: path.join(review, `${id}-opening-${seconds}.png`),
          puppeteerInstance: browser,
          browserExecutable,
        });
    } else {
      let previous = -1;
      await renderMedia({
        serveUrl,
        composition,
        codec: "h264",
        outputLocation: path.join(work, `${id}-silent.mp4`),
        puppeteerInstance: browser,
        browserExecutable,
        concurrency: 8,
        crf: 16,
        pixelFormat: "yuv420p",
        muted: true,
        imageFormat: "png",
        onProgress: ({ progress }) => {
          const pct = Math.floor(progress * 10) * 10;
          if (pct !== previous) {
            previous = pct;
            console.log(id, `${pct}%`);
          }
        },
      });
    }
  }
} finally {
  await browser.close({ silent: true });
}
