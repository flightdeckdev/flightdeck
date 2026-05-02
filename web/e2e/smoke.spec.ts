import { expect, test } from "@playwright/test";

test("home loads FlightDeck heading and timeline", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "FlightDeck", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Timeline", level: 2 })).toBeVisible();
  const timelinePre = page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: "Timeline", level: 2 }) })
    .locator("pre");
  await expect(timelinePre).toContainText('"releases"', { timeout: 30_000 });
});

test("health endpoint", async ({ request }) => {
  const res = await request.get("/health");
  expect(res.ok()).toBeTruthy();
  await expect(res.json()).resolves.toMatchObject({ status: "ok" });
});
