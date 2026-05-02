import { expect, test } from "@playwright/test";

test("home loads FlightDeck shell and overview tables", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "FlightDeck", level: 1 })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Overview" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Overview", level: 2 })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Release ID" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("No releases yet.")).toBeVisible();
});

test("hash routes reach diff and promote pages", async ({ page }) => {
  await page.goto("/#/diff");
  await expect(page.getByRole("heading", { name: "Run diff", level: 2 })).toBeVisible();
  await page.goto("/#/actions");
  await expect(page.getByRole("heading", { name: "Promote & rollback", level: 2 })).toBeVisible();
});

test("health endpoint", async ({ request }) => {
  const res = await request.get("/health");
  expect(res.ok()).toBeTruthy();
  await expect(res.json()).resolves.toMatchObject({ status: "ok" });
});
