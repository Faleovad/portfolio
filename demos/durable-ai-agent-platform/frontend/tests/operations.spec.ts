import { test, expect, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import type { Snapshot } from "../src/client";

async function click(page: Page, label: string): Promise<Snapshot> {
  const snapshot = page.waitForResponse(
    (r) => r.url().includes("/snapshot") && r.status() === 200,
  );
  const actionResponse = page.waitForResponse(
    (r) =>
      r.request().method() === "POST" &&
      (r.url().includes("/lab/") || r.url().includes("/api/manual-review/")),
  );
  void snapshot.catch(() => undefined);
  await page.getByRole("button", { name: label, exact: true }).click();
  const response = await actionResponse;
  expect(response.ok(), await response.text()).toBeTruthy();
  const result = (await (await snapshot).json()) as Snapshot;
  await expect(page.getByTestId("operation")).toHaveText("Ready");
  await expect(page.getByRole("alert")).toHaveCount(0);
  return result;
}
async function start(page: Page, scenario: string) {
  await page.goto("/");
  await expect(page.getByTestId("operation")).toHaveText("Ready");
  await page.getByLabel("EXECUTABLE SCENARIO").selectOption(scenario);
  return click(page, "Create scenario");
}
async function capture(page: Page, name: string) {
  await mkdir("../docs/screenshots", { recursive: true });
  await page.screenshot({
    path: `../docs/screenshots/${name}.png`,
    fullPage: false,
  });
}
test("normal execution with persisted evaluations", async ({ page }) => {
  await start(page, "S01");
  const data = await click(page, "Run");
  await expect(page.getByTestId("orchestrator-state")).toHaveText("COMPLETED");
  expect(data.task.model_used).toBe(1);
  expect(data.evaluations).toHaveLength(5);
  expect(data.evaluations.every((row) => row.passed)).toBeTruthy();
  await capture(page, "01-normal-task");
});
test("commit then timeout exposes three separate truth layers", async ({
  page,
}) => {
  await start(page, "S04");
  const unknown = await click(page, "Step");
  await expect(page.getByTestId("orchestrator-state")).toHaveText("UNKNOWN");
  await expect(page.getByTestId("provider-state")).toHaveText("COMMITTED");
  await expect(page.getByTestId("receipt-state")).toHaveText("NONE");
  expect(unknown.provider.mutations).toBe(1);
  expect(unknown.provider.dispatch_attempts).toBe(1);
  expect(unknown.tool_intents[0].state).toBe("UNKNOWN");
  expect(unknown.recovery_tasks[0].state).toBe("PENDING");
  await capture(page, "02-commit-then-timeout");
  const confirmed = await click(page, "Recover");
  await expect(page.getByTestId("receipt-state")).toHaveText("PRESENT");
  expect(confirmed.tool_receipts).toHaveLength(1);
  expect(confirmed.provider.mutations).toBe(1);
  expect(confirmed.provider.dispatch_attempts).toBe(1);
});
test("OS worker kill and separate recovery process", async ({ page }) => {
  await start(page, "S06");
  const unknown = await click(page, "Crash worker");
  expect(unknown.task.state).toBe("UNKNOWN");
  const operator = unknown.events.find(
    (row) => row.kind === "operator_decision",
  );
  expect(JSON.stringify(operator)).toContain("terminated_at_unknown");
  await click(page, "Restart worker");
  const final = await click(page, "Recover");
  expect(final.task.state).toBe("COMPLETED");
  expect(final.provider).toMatchObject({ mutations: 1, dispatch_attempts: 1 });
  expect(final.tool_receipts).toHaveLength(1);
  await capture(page, "03-recovery-after-restart");
});
test("foreign task UUID denied by real backend", async ({ page, request }) => {
  await start(page, "S15");
  const owner = await (
    await request.post("/api/tenants", {
      data: { name: "Foreign synthetic owner" },
    })
  ).json();
  const created = await (
    await request.post("/lab/sessions/S01", {
      headers: { Authorization: `Bearer ${owner.token}` },
    })
  ).json();
  await page.getByLabel("Task UUID from another tenant").fill(created.task_id);
  await page.getByRole("button", { name: "Check access", exact: true }).click();
  await expect(page.getByTestId("tenant-denial")).toContainText("404");
  const foreign = await request.get(`/api/tasks/${created.task_id}`, {
    headers: { Authorization: `Bearer ${owner.token}` },
  });
  expect(foreign.status()).toBe(200);
  await page
    .getByTestId("tenant-denial")
    .evaluate((element) => element.scrollIntoView({ block: "center" }));
  await capture(page, "04-tenant-access-denial");
});
test("artifact provenance reaches source document", async ({ page }) => {
  await start(page, "S02");
  const data = await click(page, "Run");
  const artifact = data.artifacts[0].content as {
    provenance: { hit_id: string; chunk_id: string; document_id: string }[];
  };
  expect(artifact.provenance.length).toBeGreaterThan(0);
  expect(
    data.retrieval_hits.some((hit) => hit.id === artifact.provenance[0].hit_id),
  ).toBeTruthy();
  expect(artifact.provenance[0].chunk_id).toMatch(/^[a-f0-9-]{36}$/);
  await page.getByRole("link", { name: /Evidence & provenance/ }).click();
  await page
    .getByRole("heading", { name: "RAG provenance" })
    .scrollIntoViewIfNeeded();
  await page.locator("#evidence summary").first().click();
  await expect(page.locator("#evidence pre").first()).toContainText(
    "provenance",
  );
  await page
    .locator("#evidence")
    .evaluate((element) => element.scrollIntoView({ block: "start" }));
  await capture(page, "05-rag-provenance");
});
test("manual review actions preserve mutation fence", async ({ page }) => {
  await start(page, "S21");
  const review = await click(page, "Run");
  expect(review.task.state).toBe("MANUAL_REVIEW");
  expect(review.tool_intents[0].state).toBe("MANUAL_REVIEW");
  const acknowledged = await click(page, "Acknowledge observation");
  expect(acknowledged.tool_intents[0].state).toBe("MANUAL_REVIEW");
  expect(acknowledged.tool_receipts).toHaveLength(0);
  expect(acknowledged.provider.dispatch_attempts).toBe(1);
  expect(
    acknowledged.events.some((row) => row.kind === "review_acknowledged"),
  ).toBeTruthy();
  await page
    .getByRole("heading", { name: "Manual review", exact: true })
    .scrollIntoViewIfNeeded();
  await capture(page, "06-manual-review");
});
test("stale worker rejected while new owner completes", async ({ page }) => {
  await start(page, "S09");
  const data = await click(page, "Run");
  expect(
    data.events.some((row) => row.kind === "stale_owner_rejected"),
  ).toBeTruthy();
  expect(data.steps[0].owner).toBe("new-owner");
  expect(data.provider.mutations).toBe(1);
  await page
    .getByRole("heading", { name: "Worker ownership", exact: true })
    .scrollIntoViewIfNeeded();
  await capture(page, "07-stale-worker-ownership");
});
test("budget exhaustion is visible and persisted", async ({ page }) => {
  await start(page, "S17");
  const data = await click(page, "Run");
  await expect(page.getByTestId("orchestrator-state")).toHaveText(
    "BUDGET_EXHAUSTED",
  );
  expect(data.model_calls).toHaveLength(0);
  expect(
    data.events.some((row) => row.kind === "budget_exhausted"),
  ).toBeTruthy();
});
test("cancellation during UNKNOWN reconciles before cancellation", async ({
  page,
}) => {
  await start(page, "S19");
  const pending = await click(page, "Step");
  expect(pending.task.state).toBe("CANCEL_REQUESTED");
  expect(pending.provider.mutations).toBe(1);
  expect(pending.tool_receipts).toHaveLength(0);
  const final = await click(page, "Recover");
  expect(final.task.state).toBe("CANCELLED");
  expect(final.tool_receipts).toHaveLength(1);
  expect(final.provider.dispatch_attempts).toBe(1);
});
test("AgentVersion remains pinned after publishing v2", async ({ page }) => {
  const initial = await start(page, "S20");
  await click(page, "Step");
  await click(page, "Step");
  const final = await click(page, "Run");
  expect(final.task.agent_version_id).toBe(initial.task.agent_version_id);
  expect(final.version.version).toBe(1);
  await expect(page.getByTestId("pinned-version")).toHaveText(
    String(initial.task.agent_version_id),
  );
});

test("quota lost ACK retains one adjustment after recovery", async ({
  page,
}) => {
  await start(page, "S45");
  const unknown = await click(page, "Step");
  expect(unknown.task.state).toBe("UNKNOWN");
  expect(unknown.provider.domain_state.quota[0].balance).toBe(100);
  await page
    .getByText("Inspect tool effects and provider domain state", {
      exact: true,
    })
    .click();
  const confirmed = await click(page, "Recover");
  expect(confirmed.tool_receipts[0].identity).toMatchObject({ tool: "quota" });
  expect(confirmed.provider.domain_state.quota[0].balance).toBe(100);
  expect(confirmed.provider.mutations).toBe(1);
  expect(confirmed.provider.dispatch_attempts).toBe(1);
});

test("external Search persists observation without a mutation receipt", async ({
  page,
}) => {
  await start(page, "S42");
  const final = await click(page, "Run");
  expect(final.task.state).toBe("COMPLETED");
  expect(final.tool_intents).toHaveLength(0);
  expect(final.tool_receipts).toHaveLength(0);
  expect(final.provider.mutations).toBe(0);
  const observation = final.artifacts.find(
    (row) => row.media_type === "application/vnd.synthetic.search+json",
  );
  expect(observation?.content).toMatchObject({ read_only: true });
});

test("mobile console executes a real task without horizontal overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await start(page, "S01");
  await click(page, "Run");
  await expect(page.getByTestId("orchestrator-state")).toHaveText("COMPLETED");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBeTruthy();
});
