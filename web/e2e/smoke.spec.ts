import { expect, test } from "@playwright/test";

test("home loads FlightDeck shell and overview tables", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "FlightDeck", level: 1 })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Overview" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Overview", level: 2 })).toBeVisible();
  await expect(page.getByRole("region", { name: "Ledger metrics" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("columnheader", { name: "Release ID" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("No releases yet.")).toBeVisible();
});

test("hash routes reach diff, runs, and promote pages", async ({ page }) => {
  await page.goto("/#/diff");
  await expect(page.getByRole("heading", { name: "Run diff", level: 2 })).toBeVisible();
  await expect(page.getByRole("region", { name: "Diff help" })).toBeVisible();
  await page.goto("/#/runs");
  await expect(page.getByRole("heading", { name: "Run events", level: 2 })).toBeVisible();
  await page.goto("/#/actions");
  await expect(page.getByRole("heading", { name: "Promote & rollback", level: 2 })).toBeVisible();
});

test("runs page requires release id before query", async ({ page }) => {
  await page.goto("/#/runs");
  await page.getByRole("button", { name: "Load runs" }).click();
  await expect(page.getByText("Release ID is required.")).toBeVisible();
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

test("security status reflects server loopback mode", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("status")).toContainText("loopback");
});
