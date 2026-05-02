import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const e2eServer = path.join(__dirname, "scripts", "e2e-server.mjs");
const port = process.env.FD_E2E_PORT || "9876";
const baseURL = `http://127.0.0.1:${port}`;

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
    reuseExistingServer: !process.env.CI,
  },
});
