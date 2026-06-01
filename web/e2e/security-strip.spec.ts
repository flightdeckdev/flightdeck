import { expect, test } from "@playwright/test";

test.describe("security strip", () => {
  test("scoped strip shows loopback chips on real /health", async ({ page }) => {
    await page.goto("/");
    const strip = page.getByTestId("security-strip");
    await expect(strip).toContainText("Loopback open");
    await expect(strip).toContainText("Writes");
  });

  test("bearer /health shows chip copy and mismatch hint when UI token unset", async ({ page }) => {
    await page.route("**/health", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "ok",
          mutation_auth: "bearer",
          read_auth: "bearer",
        }),
      });
    });
    await page.goto("/");
    const strip = page.getByTestId("security-strip");
    await expect(strip).toContainText("Bearer required");
    await expect(strip).toContainText("VITE_FLIGHTDECK_LOCAL_API_TOKEN");
  });
});
