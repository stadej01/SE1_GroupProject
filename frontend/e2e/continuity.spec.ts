import { expect, test } from "@playwright/test";

const missingDestination = `<!-- start: A -->
# A
Narrator: Start.
* "Go" -> Missing
`;

const cleanDialogue = `<!-- start: A -->
<!-- end: B -->
# A
Narrator: Start.
* "Continue" -> B
# B
Narrator: The end.
`;

const cycleDialogue = `<!-- start: A -->
# A
Narrator: A.
<<jump: B>>
# B
Narrator: B.
<<jump: C>>
# C
Narrator: C.
<<jump: A>>
`;

test("continuity check reports an unlinked choice with its source node", async ({ page }) => {
  await page.goto("/");
  await page.locator("#markdown-source").fill(missingDestination);
  await page.getByRole("button", { name: "Check continuity" }).click();

  await expect(page.locator("#continuity-status")).toHaveText("Continuity check found 1 issue");
  await expect(page.locator("#diagnostics")).toContainText("A: Target node Missing does not exist");
  await expect(page.locator("#diagnostics button")).toBeVisible();
});

test("continuity check reports a clean dialogue", async ({ page }) => {
  await page.goto("/");
  await page.locator("#markdown-source").fill(cleanDialogue);
  await page.getByRole("button", { name: "Check continuity" }).click();

  await expect(page.locator("#continuity-status")).toHaveText("Continuity check passed: no issues");
  await expect(page.locator("#diagnostics-panel")).toBeHidden();
});

test("continuity check detects a multi-node loop without hanging", async ({ page }) => {
  await page.goto("/");
  await page.locator("#markdown-source").fill(cycleDialogue);
  await page.getByRole("button", { name: "Check continuity" }).click();

  await expect(page.locator("#continuity-status")).toHaveText("Continuity check found 1 issue");
  await expect(page.locator("#diagnostics")).toContainText("Loop detected: A -> B -> C -> A");
  await expect(page.getByRole("button", { name: "Check continuity" })).toBeEnabled();
});

test("selecting an end node clears the warning and persists after reload", async ({ page }) => {
  await page.goto("/");
  await page.locator("#markdown-source").fill(cleanDialogue.replace("<!-- end: B -->\n", ""));
  await page.getByRole("button", { name: "Parse Markdown" }).click();
  await page.getByRole("button", { name: "Check continuity" }).click();
  await expect(page.locator("#continuity-status")).toHaveText("Continuity check found 1 issue");
  await expect(page.locator("#diagnostics")).toContainText("B: Node B has no outgoing choices or jumps");

  await page.locator("#end-node-summary").click();
  await page.locator("#end-node-list").getByLabel("B", { exact: true }).check();
  await expect(page.locator('.react-flow__node[data-id="B"] .dlg-node__end')).toHaveText("END");
  await page.getByRole("button", { name: "Parse Markdown" }).click();
  await expect(page.locator("#markdown-source")).toHaveValue(/<!-- end: B -->/);
  await page.getByRole("button", { name: "Check continuity" }).click();
  await expect(page.locator("#continuity-status")).toHaveText("Continuity check passed: no issues");

  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.locator("#save-status")).toContainText("saved");
  await page.reload();
  await expect(page.locator("#markdown-source")).toHaveValue(/<!-- end: B -->/);
  await page.getByRole("button", { name: "Parse Markdown" }).click();
  await expect(page.locator('.react-flow__node[data-id="B"] .dlg-node__end')).toHaveText("END");
});
