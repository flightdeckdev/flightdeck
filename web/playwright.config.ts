import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const e2eServer = path.join(__dirname, "scripts", "e2e-server.mjs");
const port = process.env.FD_E2E_PORT || "9876";
const baseURL = `http://127.0.0.1:${port}`;

/** Patch workspace YAML for approval only when that spec (or CI) requests it — not for `FD_*` alone. */
function e2eServerShouldForceApproval(): boolean {
  if (process.env.PW_WEBSERVER_APPROVAL === "1") return true;
  return process.argv.some((arg) => {
    const n = arg.replace(/\\/g, "/");
    return /(^|\/)e2e\/actions-approval\.spec\.ts$/.test(n);
  });
}

const webServerEnv = { ...process.env, PW_FORCE_APPROVAL_WORKSPACE: e2eServerShouldForceApproval() ? "1" : "0" };

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL,
    trace: "on-first-retry",
  },
  webServer: {
    command: `node "${e2eServer}"`,
    cwd: __dirname,
    url: `${baseURL}/health`,
    timeout: 120_000,
    // Always start a fresh `e2e-server` workspace so a prior local run (e.g. approval-mode)
    // cannot be reused when the default suite expects `promotion_requires_approval: false`.
    reuseExistingServer: false,
    env: webServerEnv,
  },
});
