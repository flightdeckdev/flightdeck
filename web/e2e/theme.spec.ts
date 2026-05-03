import { expect, test } from "@playwright/test";

const settingsUrl = "/#/settings";

test.describe("appearance / theme", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(settingsUrl);
    await page.evaluate(() => localStorage.removeItem("flightdeck-theme"));
    await page.reload();
  });

  test("defaults to light and shows Appearance controls on Settings", async ({ page }) => {
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await expect(page.getByRole("heading", { name: "Settings", level: 2 })).toBeVisible();
    await expect(page.getByRole("group", { name: "Appearance" })).toBeVisible();
    await expect(page.getByRole("radio", { name: "Light" })).toBeChecked();
  });

  test("dark mode sets data-theme and persists", async ({ page }) => {
    await page.getByRole("radio", { name: "Dark" }).check();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.getByRole("radio", { name: "Dark" })).toBeChecked();

    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.getByRole("radio", { name: "Dark" })).toBeChecked();
  });

  test("system mode follows prefers-color-scheme", async ({ page }) => {
    await page.getByRole("radio", { name: "System" }).check();
    await page.emulateMedia({ colorScheme: "dark" });
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    await page.emulateMedia({ colorScheme: "light" });
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });

  test("dark theme keeps shell and overview readable", async ({ page }) => {
    await page.getByRole("radio", { name: "Dark" }).check();
    await expect(page.getByRole("heading", { name: "FlightDeck", level: 1 })).toBeVisible();
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Overview", level: 2 })).toBeVisible();
    await expect(page.getByRole("region", { name: "Ledger metrics" })).toBeVisible({ timeout: 30_000 });
  });
});
