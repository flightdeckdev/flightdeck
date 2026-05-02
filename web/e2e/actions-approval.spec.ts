import { expect, test } from "@playwright/test";

test.describe("approval-required workspace (FD_E2E_FORCE_APPROVAL=1)", () => {
  test.skip(!process.env.FD_E2E_FORCE_APPROVAL, "set FD_E2E_FORCE_APPROVAL=1 (see CI workflow)");

  test("actions page shows request/confirm flow", async ({ page }) => {
    await page.goto("/#/actions");
    await expect(page.getByText("human approval required")).toBeVisible();
    await expect(page.getByRole("button", { name: "Request promotion" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Promote" })).not.toBeVisible();
    await expect(page.getByRole("heading", { name: "Pending promotion requests", level: 3 })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Confirm promotion", level: 3 })).toBeVisible();
  });

  test("GET /v1/workspace reflects approval mode", async ({ request }) => {
    const res = await request.get("/v1/workspace");
    expect(res.ok()).toBeTruthy();
    const j = await res.json();
    expect(j.promotion_requires_approval).toBe(true);
  });
});
