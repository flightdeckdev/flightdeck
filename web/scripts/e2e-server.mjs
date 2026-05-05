#!/usr/bin/env node
/**
 * Fresh workspace + `flightdeck serve` for Playwright (cross-platform).
 * CI: uses `uv run flightdeck …` when GITHUB_ACTIONS is set.
 * Local: prefer `uv run flightdeck …` when `uv.lock` exists and `uv` is on PATH so the
 * repo package + committed static bundle are used (not a stale site-packages install).
 * Fallback: `python -m flightdeck.cli.main` with PYTHONPATH pointing at `repo/src`.
 */
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..", "..");
const ws = path.join(root, ".tmp", "playwright-fd-workspace");
const port = process.env.FD_E2E_PORT || "9876";
const inCi = Boolean(process.env.GITHUB_ACTIONS);

function uvAvailable() {
  const r = spawnSync("uv", ["--version"], { encoding: "utf8" });
  return r.status === 0;
}

function useUvRun() {
  if (process.env.FLIGHTDECK_E2E_USE_UV === "0") return false;
  if (process.env.FLIGHTDECK_E2E_USE_UV === "1") return uvAvailable();
  try {
    fs.accessSync(path.join(root, "uv.lock"));
  } catch {
    return false;
  }
  return uvAvailable();
}

/** Prefer repo `src/` so `python -m flightdeck` does not pick up an unrelated pip install. */
function repoPythonEnv() {
  const srcPath = path.join(root, "src");
  const sep = path.delimiter;
  const prev = process.env.PYTHONPATH;
  const PYTHONPATH = prev ? `${srcPath}${sep}${prev}` : srcPath;
  return { ...process.env, PYTHONPATH };
}

function run(cmd, args, opts) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { stdio: "inherit", ...opts });
    child.on("error", reject);
    child.on("exit", (code, signal) => {
      if (code === 0) resolve();
      else reject(new Error(`${cmd} ${args.join(" ")} exited ${code} signal=${signal}`));
    });
  });
}

fs.rmSync(ws, { recursive: true, force: true });
fs.mkdirSync(ws, { recursive: true });

const uvRun = useUvRun();

// Minimal workspace for UI/e2e: no bundled catalog path so GET /v1/workspace matches
// smoke.spec.ts (pricing_catalog_configured: false) and actions approval tests stay predictable.
if (inCi || uvRun) {
  await run("uv", ["run", "flightdeck", "init", "--no-bundled-pricing"], { cwd: ws });
} else if (process.platform === "win32") {
  await run("py", ["-3", "-m", "flightdeck.cli.main", "init", "--no-bundled-pricing"], {
    cwd: ws,
    env: repoPythonEnv(),
  });
} else {
  const py = process.env.FLIGHTDECK_E2E_PYTHON || "python3";
  await run(py, ["-m", "flightdeck.cli.main", "init", "--no-bundled-pricing"], {
    cwd: ws,
    env: repoPythonEnv(),
  });
}

// Set by `playwright.config.ts` only when the Playwright CLI targets `e2e/actions-approval.spec.ts`
// alone — not when a shell leaks `FD_E2E_FORCE_APPROVAL=1` during the default full suite.
if (process.env.PW_FORCE_APPROVAL_WORKSPACE === "1") {
  const cfgPath = path.join(ws, "flightdeck.yaml");
  let text = fs.readFileSync(cfgPath, "utf8");
  if (/promotion_requires_approval:\s*false/.test(text)) {
    text = text.replace(/promotion_requires_approval:\s*false/, "promotion_requires_approval: true");
  } else if (!/promotion_requires_approval:\s*true/.test(text)) {
    text += "\npromotion_requires_approval: true\n";
  }
  fs.writeFileSync(cfgPath, text, "utf8");
}

let serveArgs;
let serveCmd;
let serveOpts = { cwd: ws, stdio: "inherit" };

if (inCi || uvRun) {
  serveCmd = "uv";
  serveArgs = ["run", "flightdeck", "serve", "--host", "127.0.0.1", "--port", port];
} else if (process.platform === "win32") {
  serveCmd = "py";
  serveArgs = ["-3", "-m", "flightdeck.cli.main", "serve", "--host", "127.0.0.1", "--port", port];
  serveOpts = { ...serveOpts, env: repoPythonEnv() };
} else {
  serveCmd = process.env.FLIGHTDECK_E2E_PYTHON || "python3";
  serveArgs = ["-m", "flightdeck.cli.main", "serve", "--host", "127.0.0.1", "--port", port];
  serveOpts = { ...serveOpts, env: repoPythonEnv() };
}

const serve = spawn(serveCmd, serveArgs, serveOpts);

function forward(sig) {
  try {
    serve.kill(sig);
  } catch {
    /* ignore */
  }
}
process.on("SIGTERM", () => forward("SIGTERM"));
process.on("SIGINT", () => forward("SIGINT"));

serve.on("exit", (code, signal) => {
  if (signal) process.exit(0);
  process.exit(code ?? 1);
});
