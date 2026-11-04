import { expect, test } from "@playwright/test";

const source = "# A\nNarrator: First.\n\n# B\nNarrator: Second.\n";

test("warns when no starting node is selected", async ({ page }) => {
  page.on("dialog", dialog => dialog.accept());
  await page.goto("/");
  await page.locator("#markdown-source").fill(source);
  await page.getByRole("button", { name: "Parse Markdown" }).click();

  await expect(page.locator(".react-flow__node")).toHaveCount(2);
  await expect(page.locator("#diagnostics")).toContainText("Starting nodes have not been allocated");
  await expect(page.locator(".dlg-node__start")).toHaveCount(0);
});

test("selects and persists one starting node", async ({ page }) => {
  page.on("dialog", dialog => dialog.accept());
  await page.goto("/");
  await page.locator("#markdown-source").fill(source);
  await page.getByRole("button", { name: "Parse Markdown" }).click();

  await page.locator(".starting-node-picker summary").click();
  await page.getByLabel("B", { exact: true }).check();
  await expect(page.locator('.react-flow__node[data-id="B"] .dlg-node__start')).toHaveText("START");

  await page.getByRole("button", { name: "Parse Markdown" }).click();
  const expectedSource = `<!-- start: B -->\n${source}`;
  await expect(page.locator("#markdown-source")).toHaveValue(expectedSource);
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator("#save-status")).toHaveText("Draft saved");

  await page.reload();
  await expect(page.locator("#markdown-source")).toHaveValue(expectedSource);
  await page.getByRole("button", { name: "Parse Markdown" }).click();
  await expect(page.locator('.react-flow__node[data-id="B"] .dlg-node__start')).toHaveText("START");
  await expect(page.locator('.react-flow__node[data-id="A"] .dlg-node__start')).toHaveCount(0);
});

test("allows multiple starting nodes", async ({ page }) => {
  page.on("dialog", dialog => dialog.accept());
  await page.goto("/");
  await page.locator("#markdown-source").fill(source);
  await page.getByRole("button", { name: "Parse Markdown" }).click();

  await page.locator(".starting-node-picker summary").click();
  await page.getByLabel("A", { exact: true }).check();
  await page.getByLabel("B", { exact: true }).check();
  await expect(page.locator(".dlg-node__start")).toHaveCount(2);

  await page.getByRole("button", { name: "Parse Markdown" }).click();
  await expect(page.locator("#markdown-source")).toHaveValue(`<!-- start: A -->\n<!-- start: B -->\n${source}`);
});