#!/usr/bin/env node
/**
 * Starts a fresh FlightDeck workspace + serve, then records a short Playwright
 * walkthrough (WebM) and viewport screenshots for marketing / LinkedIn.
 *
 * Usage (from repo root, after `uv sync`):
 *   node web/scripts/capture-demo-artifacts.mjs
 *
 * Env:
 *   FD_DEMO_ARTIFACT_DIR  output directory (default: <repo>/artifacts/flightdeck-demo-share)
 */
import { execFile, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { chromium } from "playwright-core";

const execFileAsync = promisify(execFile);

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..", "..");
const fdBin = path.join(repoRoot, ".venv", "bin", "flightdeck");
const outDir = process.env.FD_DEMO_ARTIFACT_DIR || path.join(repoRoot, "artifacts", "flightdeck-demo-share");
const ws = path.join(fs.mkdtempSync(path.join("/tmp", "fd-demo-")));
const port = process.env.FD_DEMO_PORT || "10088";
const base = `http://127.0.0.1:${port}`;

async function waitForHealth(maxMs = 60_000) {
  const deadline = Date.now() + maxMs;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`${base}/health`);
      if (r.ok) return;
    } catch {
      /* retry */
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error("Timed out waiting for /health");
}

function killServe(child) {
  try {
    child.kill("SIGTERM");
  } catch {
    /* ignore */
  }
}

async function main() {
  if (!fs.existsSync(fdBin)) {
    throw new Error(`Missing ${fdBin} — run: uv sync --frozen --extra dev`);
  }

  fs.mkdirSync(outDir, { recursive: true });

  await execFileAsync(fdBin, ["init", "--no-bundled-pricing"], { cwd: ws, stdio: "inherit" });

  const serve = spawn(fdBin, ["serve", "--host", "127.0.0.1", "--port", port], {
    cwd: ws,
    stdio: "ignore",
    detached: false,
  });

  let exitCode = 0;
  try {
    await waitForHealth();

    const browser = await chromium.launch({
      headless: true,
      args: ["--no-sandbox", "--disable-dev-shm-usage"],
    });

    const videoDir = path.join(outDir, "_video_tmp");
    fs.rmSync(videoDir, { recursive: true, force: true });
    fs.mkdirSync(videoDir, { recursive: true });

    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      recordVideo: { dir: videoDir, size: { width: 1440, height: 900 } },
    });
    const page = await context.newPage();
    page.setDefaultTimeout(45_000);

    const dwell = (ms) => page.waitForTimeout(ms);

    const shot = async (name) => {
      const p = path.join(outDir, name);
      await page.screenshot({ path: p, type: "png" });
      return p;
    };

    // Overview — security chips + nav (hold for viewers)
    await page.goto(`${base}/#/`, { waitUntil: "networkidle" });
    await page.getByRole("heading", { name: "Overview", level: 2 }).waitFor({ state: "visible" });
    await page.getByRole("status").filter({ hasText: "Loopback open" }).waitFor({ state: "visible" });
    await dwell(2200);
    await shot("01-overview-loopback-chips.png");

    await page.getByTestId("ledger-metrics-toggle").click();
    await page.getByRole("region", { name: "Ledger metrics" }).waitFor({ state: "visible" });
    await dwell(1800);
    await shot("02-overview-ledger-metrics.png");

    // Diff
    await page.goto(`${base}/#/diff`, { waitUntil: "networkidle" });
    await page.getByRole("heading", { name: "Run diff", level: 2 }).waitFor({ state: "visible" });
    await dwell(1800);
    await shot("03-diff-compute.png");

    // Runs
    await page.goto(`${base}/#/runs`, { waitUntil: "networkidle" });
    await page.getByRole("heading", { name: "Run events", level: 2 }).waitFor({ state: "visible" });
    await dwell(1800);
    await shot("04-runs-query.png");

    // Actions
    await page.goto(`${base}/#/actions`, { waitUntil: "networkidle" });
    await page.getByRole("heading", { name: "Promote & rollback", level: 2 }).waitFor({ state: "visible" });
    await dwell(1800);
    await shot("05-actions-promote.png");

    // Settings — dark theme (shows theme-color / polish)
    await page.goto(`${base}/#/settings`, { waitUntil: "networkidle" });
    await page.getByRole("heading", { name: "Settings", level: 2 }).waitFor({ state: "visible" });
    await dwell(900);
    await page.getByRole("radio", { name: "Dark" }).check();
    await dwell(2000);
    await shot("06-settings-dark-theme.png");

    await page.goto(`${base}/#/`, { waitUntil: "networkidle" });
    await page.getByRole("heading", { name: "Overview", level: 2 }).waitFor({ state: "visible" });
    await dwell(2200);

    await context.close();
    await browser.close();

    const webms = fs.readdirSync(videoDir).filter((f) => f.endsWith(".webm"));
    const rawVideo = webms.length ? path.join(videoDir, webms[0]) : null;
    const webmOut = path.join(outDir, "flightdeck-ui-demo.webm");
    const mp4Out = path.join(outDir, "flightdeck-ui-demo.mp4");

    if (rawVideo) {
      fs.renameSync(rawVideo, webmOut);
    }
    fs.rmSync(videoDir, { recursive: true, force: true });

    if (fs.existsSync(webmOut)) {
      await execFileAsync(
        "ffmpeg",
        ["-y", "-i", webmOut, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4Out],
        { stdio: "inherit" },
      );
    }

    // eslint-disable-next-line no-console
    console.log(`\nArtifacts written to:\n  ${outDir}\n`);
    for (const f of fs.readdirSync(outDir)) {
      // eslint-disable-next-line no-console
      console.log(`  - ${f}`);
    }
  } catch (e) {
    exitCode = 1;
    // eslint-disable-next-line no-console
    console.error(e);
  } finally {
    killServe(serve);
    try {
      await promisify(serve.once.bind(serve))("exit");
    } catch {
      /* ignore */
    }
    fs.rmSync(ws, { recursive: true, force: true });
  }
  process.exit(exitCode);
}

main();
