#!/usr/bin/env node
/**
 * Fresh workspace + `flightdeck serve` for Playwright (cross-platform).
 * CI: uses `uv run flightdeck …` when GITHUB_ACTIONS is set.
 * Local: `python -m flightdeck.cli.main` or Windows `py -3 -m flightdeck.cli.main`.
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..", "..");
const ws = path.join(root, ".tmp", "playwright-fd-workspace");
const port = process.env.FD_E2E_PORT || "9876";
const inCi = Boolean(process.env.GITHUB_ACTIONS);

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

if (inCi) {
  await run("uv", ["run", "flightdeck", "init"], { cwd: ws });
} else if (process.platform === "win32") {
  await run("py", ["-3", "-m", "flightdeck.cli.main", "init"], { cwd: ws });
} else {
  await run("python", ["-m", "flightdeck.cli.main", "init"], { cwd: ws });
}

let serveArgs;
if (inCi) {
  serveArgs = ["run", "flightdeck", "serve", "--host", "127.0.0.1", "--port", port];
} else if (process.platform === "win32") {
  serveArgs = ["-3", "-m", "flightdeck.cli.main", "serve", "--host", "127.0.0.1", "--port", port];
} else {
  serveArgs = ["-m", "flightdeck.cli.main", "serve", "--host", "127.0.0.1", "--port", port];
}

const serveCmd = inCi ? "uv" : process.platform === "win32" ? "py" : "python";
const serve = spawn(serveCmd, serveArgs, { cwd: ws, stdio: "inherit" });

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
