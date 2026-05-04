import { expect, test } from "@playwright/test";

const mockReleaseRow = {
  release_id: "rel_e2e_wireframe",
  agent_id: "support-bot",
  version: "1.0.0",
  environment: "local",
  checksum: "sha256deadbeef",
  created_at: "2026-01-01T12:00:00Z",
};

const mockDiffPass = {
  policy: {
    passed: true,
    reasons: [] as string[],
    evaluated_at: "2026-01-02T00:00:00Z",
  },
  samples: {
    baseline_runs: 10,
    candidate_runs: 12,
    confidence: "medium",
  },
  metrics: {
    baseline_cost_per_run_usd: 0.012,
    candidate_cost_per_run_usd: 0.015,
    delta_cost_per_run_usd: 0.003,
    delta_cost_per_run_pct: 0.25,
    baseline_latency_ms_avg: 100,
    candidate_latency_ms_avg: 110,
    delta_latency_ms_avg: 10,
    baseline_error_rate: 0.01,
    candidate_error_rate: 0.02,
    delta_error_rate: 0.01,
  },
  pricing: {
    baseline_provider: "openai",
    baseline_version: "2026-01",
    baseline_model: "gpt-4.1",
    candidate_provider: "openai",
    candidate_version: "2026-01",
    candidate_model: "gpt-4.1-mini",
    pricing_or_model_changed: true,
    warnings: ["Synthetic pricing warning for e2e."],
    hints: [] as string[],
    prices: {
      baseline_input_usd_per_1k_tokens: 0.005,
      baseline_output_usd_per_1k_tokens: 0.015,
      candidate_input_usd_per_1k_tokens: 0.002,
      candidate_output_usd_per_1k_tokens: 0.008,
    },
  },
};

test.describe("overview copy & mocked diff interactions", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/v1/releases", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ releases: [mockReleaseRow] }),
      });
    });
    await page.route("**/v1/promoted", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ promoted: [] }),
      });
    });
    await page.route("**/v1/actions", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ actions: [] }),
      });
    });
    await page.route("**/v1/diff", async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      const postData = route.request().postDataJSON() as { baseline_release_id?: string } | null;
      const baseline = postData?.baseline_release_id ?? "";
      let body: typeof mockDiffPass & { policy: { passed: boolean; reasons: string[]; evaluated_at: string } };
      if (baseline.includes("fail_gate")) {
        body = {
          ...mockDiffPass,
          policy: {
            passed: false,
            reasons: ["cost regression exceeds threshold", "secondary reason"],
            evaluated_at: "2026-01-02T00:00:00Z",
          },
        };
      } else {
        body = mockDiffPass;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(body),
      });
    });
  });

  test("overview copy release ID shows transient copied state", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("columnheader", { name: "Primary" })).toBeVisible({ timeout: 30_000 });
    const copyBtn = page.getByTestId("overview-copy-release-row");
    await expect(copyBtn).toBeVisible();
    await copyBtn.click();
    await expect(copyBtn).toHaveText("Copied");
    await expect(copyBtn).toHaveText("Copy", { timeout: 4000 });
  });

  test("diff with mocked POST shows twin, policy PASS, decision CTA, pricing expand", async ({ page }) => {
    await page.goto("/#/diff?baseline=rel_a&candidate=rel_b&environment=local&window=7d");
    await page.getByRole("button", { name: "Compute diff" }).click();
    await expect(page.getByRole("heading", { name: "Policy evaluation", level: 3 })).toBeVisible();
    await expect(page.locator(".fd-policy-panel").getByText("PASS", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Decision", level: 3 })).toBeVisible();
    await expect(page.getByRole("link", { name: "Continue to promote" })).toBeVisible();
    const expand = page.getByTestId("diff-pricing-expand");
    await expect(expand).toBeVisible();
    await expect(page.getByTestId("diff-per-1k-prices-title")).not.toBeVisible();
    await expand.click();
    await expect(page.getByTestId("diff-per-1k-prices-title")).toBeVisible();
    await expect(page.getByText("Synthetic pricing warning for e2e.")).toBeVisible();
  });

  test("diff with mocked FAIL shows blocked strip and no promote CTA", async ({ page }) => {
    await page.goto("/#/diff?baseline=rel_fail_gate&candidate=rel_b&environment=local&window=7d");
    await page.getByRole("button", { name: "Compute diff" }).click();
    await expect(page.getByText(/^Blocked:/)).toBeVisible();
    await expect(page.locator(".fd-diff-block-strip").getByText("cost regression exceeds threshold")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Policy evaluation", level: 3 })).toBeVisible();
    await expect(page.locator(".fd-policy-panel").getByText("FAIL", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Continue to promote" })).not.toBeVisible();
  });
});
