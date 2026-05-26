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
const inCi = Boolean(process.env.GITHUB_ACTIONS);
const outDir = process.env.FD_DEMO_ARTIFACT_DIR || path.join(repoRoot, "artifacts", "flightdeck-demo-share");
const ws = path.join(fs.mkdtempSync(path.join("/tmp", "fd-demo-")));
const port = process.env.FD_DEMO_PORT || "10088";
const base = `http://127.0.0.1:${port}`;

function resolveFlightdeckRunner() {
  const venvBin = path.join(repoRoot, ".venv", "bin", "flightdeck");
  if (fs.existsSync(venvBin)) {
    return { mode: "direct", bin: venvBin };
  }
  if (inCi) return { mode: "uv", bin: "uv" };
  if (process.platform === "win32") {
    return { mode: "py", bin: "py" };
  }
  const py = process.env.FLIGHTDECK_E2E_PYTHON || "python3";
  return { mode: "python", bin: py };
}

async function flightdeckInit(cwd) {
  const r = resolveFlightdeckRunner();
  if (r.mode === "direct") {
    await execFileAsync(r.bin, ["init", "--no-bundled-pricing"], { cwd, stdio: "inherit" });
    return;
  }
  if (r.mode === "uv") {
    await execFileAsync("uv", ["run", "flightdeck", "init", "--no-bundled-pricing"], { cwd, stdio: "inherit" });
    return;
  }
  if (r.mode === "py") {
    await execFileAsync(r.bin, ["-3", "-m", "flightdeck.cli.main", "init", "--no-bundled-pricing"], {
      cwd,
      stdio: "inherit",
    });
    return;
  }
  await execFileAsync(r.bin, ["-m", "flightdeck.cli.main", "init", "--no-bundled-pricing"], {
    cwd,
    stdio: "inherit",
  });
}

function spawnFlightdeckServe(cwd, p) {
  const r = resolveFlightdeckRunner();
  if (r.mode === "direct") {
    return spawn(r.bin, ["serve", "--host", "127.0.0.1", "--port", p], { cwd, stdio: "ignore" });
  }
  if (r.mode === "uv") {
    return spawn("uv", ["run", "flightdeck", "serve", "--host", "127.0.0.1", "--port", p], { cwd, stdio: "ignore" });
  }
  if (r.mode === "py") {
    return spawn(r.bin, ["-3", "-m", "flightdeck.cli.main", "serve", "--host", "127.0.0.1", "--port", p], {
      cwd,
      stdio: "ignore",
    });
  }
  return spawn(r.bin, ["-m", "flightdeck.cli.main", "serve", "--host", "127.0.0.1", "--port", p], {
    cwd,
    stdio: "ignore",
  });
}

async function waitForHealth(maxMs = 60_000) {
  const deadline = Date.now() + maxMs;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`${base}/health`);
      if (r.ok) return;
    } catch {
      /* retry */
    }
    await new Promise((res) => setTimeout(res, 250));
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

async function dwell(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function main() {
  fs.mkdirSync(outDir, { recursive: true });

  await flightdeckInit(ws);

  const serve = spawnFlightdeckServe(ws, port);

  let exitCode = 0;
  let browser = null;
  try {
    await waitForHealth();

    browser = await chromium.launch({
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
    try {
      const page = await context.newPage();
      page.setDefaultTimeout(45_000);

      const shot = async (name) => {
        const p = path.join(outDir, name);
        await page.screenshot({ path: p, type: "png" });
        return p;
      };

      await page.goto(`${base}/#/`, { waitUntil: "networkidle" });
      await page.getByRole("heading", { name: "Overview", level: 2 }).waitFor({ state: "visible" });
      await page.getByTestId("security-strip").getByText("Loopback open").waitFor({ state: "visible" });
      await dwell(2200);
      await shot("01-overview-loopback-chips.png");

      await page.getByTestId("ledger-metrics-toggle").click();
      await page.getByRole("region", { name: "Ledger metrics" }).waitFor({ state: "visible" });
      await dwell(1800);
      await shot("02-overview-ledger-metrics.png");

      await page.goto(`${base}/#/diff`, { waitUntil: "networkidle" });
      await page.getByRole("heading", { name: "Run diff", level: 2 }).waitFor({ state: "visible" });
      await dwell(1800);
      await shot("03-diff-compute.png");

      await page.goto(`${base}/#/runs`, { waitUntil: "networkidle" });
      await page.getByRole("heading", { name: "Run events", level: 2 }).waitFor({ state: "visible" });
      await dwell(1800);
      await shot("04-runs-query.png");

      await page.goto(`${base}/#/actions`, { waitUntil: "networkidle" });
      await page.getByRole("heading", { name: "Promote & rollback", level: 2 }).waitFor({ state: "visible" });
      await dwell(1800);
      await shot("05-actions-promote.png");

      await page.goto(`${base}/#/`, { waitUntil: "networkidle" });
      await page.getByTestId("sidebar-settings-trigger").click();
      await page.getByRole("dialog", { name: "Appearance" }).waitFor({ state: "visible" });
      await dwell(900);
      await page.getByRole("radio", { name: "Dark" }).check();
      await dwell(2000);
      await shot("06-settings-dark-theme.png");

      await page.keyboard.press("Escape");
      await dwell(300);
      await page.goto(`${base}/#/`, { waitUntil: "networkidle" });
      await page.getByRole("heading", { name: "Overview", level: 2 }).waitFor({ state: "visible" });
      await dwell(2200);
    } finally {
      try {
        await context.close();
      } catch {
        /* ignore */
      }
      try {
        await browser.close();
      } catch {
        /* ignore */
      }
    }

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
    if (browser) {
      try {
        await browser.close();
      } catch {
        /* ignore */
      }
    }
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
