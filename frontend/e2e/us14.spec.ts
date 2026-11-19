 import { expect, test, type Page } from "@playwright/test";

const source = [
  "<!-- start: A -->",
  "# A",
  "Narrator: Hello.",
  '* "Go to B" -> B',
  "<<jump: C>>",
  "",
  "# B",
  "Narrator: Branch B.",
  '* "Finish" -> C',
  "",
  "# C",
  "Narrator: Ending.",
  "",
  "# D",
  "Narrator: Untouched."
].join("\n");

const undoKey = "ControlOrMeta+z";

function node(page: Page, id: string) {
  return page.locator(`.react-flow__node[data-id="${id}"]`);
}

function deleteButton(page: Page) {
  return page.getByRole("button", {
    name: /^Delete selected/
  });
}

async function setup(page: Page) {
  await page.goto("/");

  await page.locator("#markdown-source").fill(source);

  await page.getByRole("button", {
    name: "Parse Markdown"
  }).click();

  await expect(page.locator(".react-flow__node"))
    .toHaveCount(4);

  await expect(page.locator(".react-flow__edge"))
    .toHaveCount(3);
}

async function deleteNode(page: Page, id: string) {
  await node(page, id).click();

  // B and C are connected and require confirmation.
  page.once("dialog", dialog => {
    void dialog.accept();
  });

  await deleteButton(page).click();
}

// AC1: Multiple selection in visual graph
test("US-14 AC1: deletes multiple selected nodes in the GUI", async ({ page }) => {
  await setup(page);

  // Select the first node
  await node(page, "B").click();

  // Close the editor panel without clearing the graph selection
  await page.getByRole("button", {
    name: "Close node details"
  }).click();

  // Add the second node to the selection
  await node(page, "C").click({ modifiers: ["Shift"] });

  // Verify both nodes are selected
  await expect(deleteButton(page))
    .toHaveText("Delete selected (2)");

  await expect(deleteButton(page))
    .toHaveText("Delete selected (2)");

  page.once("dialog", dialog => {
    void dialog.accept();
  });

  await deleteButton(page).click();

  await expect(page.locator(".react-flow__node"))
    .toHaveCount(2);

  await expect(node(page, "A")).toBeVisible();
  await expect(node(page, "D")).toBeVisible();

  await expect(page.locator(".react-flow__edge"))
    .toHaveCount(0);
});

// AC2: Confirmation identifies references and allows cancel
test("US-14 AC2: identifies referencing nodes and allows cancellation", async ({ page }) => {
  await setup(page);

  await node(page, "B").click();

  let confirmation = "";

  page.once("dialog", async dialog => {
    confirmation = dialog.message();
    await dialog.dismiss();
  });

  await deleteButton(page).click();

  // The dialog identifies the selected node and reference.
  expect(confirmation).toContain("B");
  expect(confirmation).toContain("A");
  expect(confirmation).toContain("A → B");

  // Cancel must preserve everything.
  await expect(page.locator(".react-flow__node"))
    .toHaveCount(4);

  await expect(page.locator(".react-flow__edge"))
    .toHaveCount(3);

  await expect(page.locator("#markdown-source"))
    .toHaveValue(source);
});

// AC3: Undo before Markdown synchronization
test("US-14 AC3: Undo restores deleted nodes and connections", async ({ page }) => {
  await setup(page);

  await deleteNode(page, "B");

  await expect(node(page, "B")).toHaveCount(0);
  await expect(page.locator(".react-flow__edge"))
    .toHaveCount(1);

  await page.keyboard.press(undoKey);

  // Restore node B, its dialogue, choice, and edges.
  await expect(node(page, "B")).toBeVisible();
  await expect(node(page, "B")).toContainText("Branch B");

  await expect(page.locator(".react-flow__edge"))
    .toHaveCount(3);

  // Unsynced Markdown should still be original.
  await expect(page.locator("#markdown-source"))
    .toHaveValue(source);
});

// AC3: Undo after synchronization
test("US-14 AC3: Delete then Parse then Undo restores both views", async ({ page }) => {
  await setup(page);

  await deleteNode(page, "B");

  await page.getByRole("button", {
    name: "Parse Markdown"
  }).click();

  // Wait until Markdown actually reflects the deletion
  await expect(page.locator("#markdown-source"))
    .not.toHaveValue(/^# B$/m);

  // Confirm Node B is also absent from the graph
  await expect(node(page, "B")).toHaveCount(0);

  await page.keyboard.press(undoKey);

  // Both views should be restored.
  await expect(node(page, "B")).toBeVisible();
  await expect(page.locator(".react-flow__edge"))
    .toHaveCount(3);

  await expect(page.locator("#markdown-source"))
    .toHaveValue(source);

  // The restored choice and dialogue are present.
  await expect(node(page, "B"))
    .toContainText("Branch B");

  expect(await page.locator("#markdown-source").inputValue())
    .toContain('"Finish" -> C');
});

// AC4: No undo history
test("US-14 AC4: Undo with empty history leaves project unchanged", async ({ page }) => {
  await setup(page);

  // Move keyboard focus away from Markdown.
  await page.getByRole("button", {
    name: "Parse Markdown"
  }).focus();

  await page.keyboard.press(undoKey);

  await expect(page.locator(".react-flow__node"))
    .toHaveCount(4);

  await expect(page.locator(".react-flow__edge"))
    .toHaveCount(3);

  await expect(page.locator("#markdown-source"))
    .toHaveValue(source);
});

// AC5: Deleted node is removed from both representations
test("US-14 AC5: deletion is reflected in graph and Markdown after Parse", async ({ page }) => {
  await setup(page);

  await deleteNode(page, "B");

  await page.getByRole("button", {
    name: "Parse Markdown"
  }).click();

  await expect(node(page, "B")).toHaveCount(0);
  await expect(node(page, "A")).toBeVisible();
  await expect(node(page, "C")).toBeVisible();
  await expect(node(page, "D")).toBeVisible();

  await expect(page.locator(".react-flow__edge"))
    .toHaveCount(1);

  await expect(page.locator("#markdown-source"))
  .not.toHaveValue(/^# B$/m);

  const updated = await page.locator("#markdown-source")
    .inputValue();

  expect(updated).not.toContain('"Go to B" -> B');
  expect(updated).not.toContain('"Finish" -> C');

  expect(updated).toContain("# D");
  expect(updated).toContain("Narrator: Untouched.");
});

// AC6: Repeated Undo in reverse order
test("US-14 AC6: multiple Undo actions restore changes in reverse order", async ({ page }) => {
  await setup(page);

  // First deletion: B
  await deleteNode(page, "B");
  await expect(node(page, "B")).toHaveCount(0);

  // Second deletion: C
  await deleteNode(page, "C");
  await expect(node(page, "C")).toHaveCount(0);

  await expect(page.locator(".react-flow__node"))
    .toHaveCount(2);

  // First Undo restores C, but not B.
  await page.keyboard.press(undoKey);

  await expect(node(page, "C")).toBeVisible();
  await expect(node(page, "B")).toHaveCount(0);

  // Second Undo restores B.
  await page.keyboard.press(undoKey);

  await expect(node(page, "B")).toBeVisible();
  await expect(node(page, "C")).toBeVisible();

  await expect(page.locator(".react-flow__node"))
    .toHaveCount(4);

  await expect(page.locator(".react-flow__edge"))
    .toHaveCount(3);
});
