import { expect, test } from "@playwright/test";

test.describe("sidebar collapse", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => localStorage.removeItem("flightdeck-sidebar-collapsed"));
    await page.reload();
  });

  test("collapse toggle persists layout preference", async ({ page }) => {
    await page.getByRole("button", { name: "Collapse sidebar" }).click();
    await expect(page.locator("aside.fd-sidebar.fd-sidebar--collapsed")).toHaveCount(1);

    await page.reload();
    await expect(page.locator("aside.fd-sidebar.fd-sidebar--collapsed")).toHaveCount(1);

    await page.getByRole("button", { name: "Expand sidebar" }).click();
    await expect(page.locator("aside.fd-sidebar.fd-sidebar--collapsed")).toHaveCount(0);
  });
});
