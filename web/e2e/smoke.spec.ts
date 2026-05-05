import { expect, test } from "@playwright/test";

test("home loads FlightDeck shell and overview tables", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "FlightDeck", level: 1 })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Overview" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Overview", level: 2 })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Release governance workflow" })).toBeVisible();
  await expect(page.getByTestId("ledger-metrics-toggle")).toBeVisible({ timeout: 30_000 });
  await page.getByTestId("ledger-metrics-toggle").click();
  await expect(page.getByRole("region", { name: "Ledger metrics" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Primary" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("No releases yet.")).toBeVisible();
});

test("hash routes reach diff, runs, settings, and promote pages", async ({ page }) => {
  await page.goto("/#/diff");
  await expect(page.getByRole("heading", { name: "Run diff", level: 2 })).toBeVisible();
  await expect(page.getByRole("region", { name: "Diff help" })).toBeVisible();
  await page.goto("/#/runs");
  await expect(page.getByRole("heading", { name: "Run events", level: 2 })).toBeVisible();
  await page.goto("/#/settings");
  await expect(page.getByRole("heading", { name: "Settings", level: 2 })).toBeVisible();
  await page.goto("/#/actions");
  await expect(page.getByRole("heading", { name: "Promote & rollback", level: 2 })).toBeVisible();
});

test("runs page requires release id before query", async ({ page }) => {
  await page.goto("/#/runs");
  await page.getByRole("button", { name: "Load runs" }).click();
  await expect(page.getByText("Release ID is required.")).toBeVisible();
});

test("deep links prefill diff, runs, and promote forms from query params", async ({ page }) => {
  await page.goto("/#/diff?baseline=rel_base&candidate=rel_cand&environment=staging&window=14d");
  await expect(page.getByRole("textbox", { name: /baseline release id/i })).toHaveValue("rel_base");
  await expect(page.getByRole("textbox", { name: /candidate release id/i })).toHaveValue("rel_cand");
  await expect(page.getByRole("textbox", { name: /^environment$/i })).toHaveValue("staging");
  await expect(page.getByRole("textbox", { name: /^window$/i })).toHaveValue("14d");

  await page.goto("/#/runs?release_id=rel_run&environment=prod&window=30d");
  await expect(page.getByLabel(/release id/i)).toHaveValue("rel_run");
  await expect(page.getByLabel(/environment \(optional\)/i)).toHaveValue("prod");
  await expect(page.getByLabel(/^window$/i)).toHaveValue("30d");

  await page.goto("/#/actions?release_id=rel_act&environment=qa&window=1d");
  await expect(page.getByLabel(/^release id$/i)).toHaveValue("rel_act");
  await expect(page.getByLabel(/^environment$/i)).toHaveValue("qa");
  await expect(page.getByLabel(/^window$/i)).toHaveValue("1d");
});

test("GET /v1/workspace returns WorkspacePublic", async ({ request }) => {
  const res = await request.get("/v1/workspace");
  expect(res.ok()).toBeTruthy();
  const j = await res.json();
  expect(j).toMatchObject({
    api_version: "v1",
    kind: "WorkspacePublic",
    promotion_requires_approval: false,
    pricing_catalog_configured: false,
  });
  expect(typeof j.server_version).toBe("string");
  expect(j.server_version.length).toBeGreaterThan(0);
});

test("actions page shows direct Promote when approval off", async ({ page }) => {
  await page.goto("/#/actions");
  await expect(page.getByText("direct promotion")).toBeVisible();
  await expect(page.getByRole("button", { name: "Promote" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Request promotion" })).not.toBeVisible();
});

test("health endpoint", async ({ request }) => {
  const res = await request.get("/health");
  expect(res.ok()).toBeTruthy();
  await expect(res.json()).resolves.toMatchObject({
    status: "ok",
    mutation_auth: "loopback",
    read_auth: "open",
  });
});

test("bundled app icon is reachable via hashed /assets URL", async ({ page, request }) => {
  await page.goto("/");
  const href = await page.locator('link[rel="icon"]').getAttribute("href");
  expect(href).toBeTruthy();
  expect(href).toMatch(/^\/assets\/flightdeck-icon-[A-Za-z0-9_-]+\.png$/);
  const res = await request.get(href!);
  expect(res.ok()).toBeTruthy();
  expect((res.headers()["content-type"] ?? "").toLowerCase()).toContain("image/png");
});

test("stable root icon URL for favicon crawlers", async ({ request }) => {
  const res = await request.get("/flightdeck-icon.png");
  expect(res.ok()).toBeTruthy();
  expect((res.headers()["content-type"] ?? "").toLowerCase()).toContain("image/png");
});

test("security status reflects server loopback mode", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("status")).toContainText("loopback");
});
