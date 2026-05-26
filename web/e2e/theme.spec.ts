import { expect, test, type Page } from "@playwright/test";

async function openAppearanceMenu(page: Page) {
  await page.goto("/");
  await page.getByTestId("sidebar-settings-trigger").click();
  await expect(page.getByRole("dialog", { name: "Appearance" })).toBeVisible();
}

test.describe("appearance / theme", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => localStorage.removeItem("flightdeck-theme"));
    await page.reload();
  });

  test("defaults to light and shows Appearance in sidebar menu", async ({ page }) => {
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute("content", "#f3f4f6");
    await openAppearanceMenu(page);
    await expect(page.getByRole("group", { name: "Appearance" })).toBeVisible();
    await expect(page.getByRole("radio", { name: "Light" })).toBeChecked();
  });

  test("dark mode sets data-theme and persists", async ({ page }) => {
    await openAppearanceMenu(page);
    await page.getByRole("radio", { name: "Dark" }).check();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute("content", "#0c0f14");
    await expect(page.getByRole("radio", { name: "Dark" })).toBeChecked();

    await page.reload();
    await openAppearanceMenu(page);
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.getByRole("radio", { name: "Dark" })).toBeChecked();
  });

  test("system mode follows prefers-color-scheme", async ({ page }) => {
    await openAppearanceMenu(page);
    await page.getByRole("radio", { name: "System" }).check();
    await page.emulateMedia({ colorScheme: "dark" });
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    await page.emulateMedia({ colorScheme: "light" });
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });

  test("dark theme keeps shell and overview readable", async ({ page }) => {
    await openAppearanceMenu(page);
    await page.getByRole("radio", { name: "Dark" }).check();
    await expect(page.getByRole("heading", { name: "FlightDeck", level: 1 })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "Appearance" })).not.toBeVisible();
    await expect(page.getByRole("heading", { name: "Overview", level: 2 })).toBeVisible();
    await expect(page.getByTestId("ledger-metrics-toggle")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("ledger-metrics-toggle").click();
    await expect(page.getByRole("region", { name: "Ledger metrics" })).toBeVisible();
  });
});
