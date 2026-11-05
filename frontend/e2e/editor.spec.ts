import { expect, test } from "@playwright/test";

test("Django page parses, maps node selection, and refreshes dialogue-only edits", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Markdown", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Parse Markdown" }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(6);
  await expect(page.locator(".react-flow__edge")).toHaveCount(11);
  const greeting = page.locator('.react-flow__node[data-id="Node_Merchant_Greeting"]');
  await greeting.click();
  const selected = await page.locator("#markdown-source").evaluate((textarea: HTMLTextAreaElement) =>
    textarea.value.slice(textarea.selectionStart, textarea.selectionEnd));
  expect(selected).toContain("# Node_Merchant_Greeting");
  expect(selected).not.toContain("# Node_Merchant_Annoyed");
  const original = await page.locator("#markdown-source").inputValue();
  await page.locator("#markdown-source").fill(original.replace("Ah, welcome back, traveler!", "Welcome to our updated shop!"));
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  await page.getByRole("button", { name: "Parse Markdown" }).click();
  await expect(greeting).toContainText("Welcome to our updated shop!");
  await expect(page.locator(".react-flow__edge")).toHaveCount(11);
  expect(errors).toEqual([]);
});

test("invalid Markdown saves and reloads but cannot produce a graph", async ({ page }) => {
  await page.goto("/");
  const invalid = "# A\nNarrator: Still editable.\n??? unsupported syntax";
  await page.locator("#markdown-source").fill(invalid);
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.locator("#save-status")).toHaveText("Draft saved");
  await page.getByRole("button", { name: "Parse Markdown" }).click();
  await expect(page.locator("#diagnostics")).toContainText("Line 3:");
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  await page.getByRole("button", { name: /Line 3:/ }).click();
  const selected = await page.locator("#markdown-source").evaluate((textarea: HTMLTextAreaElement) =>
    textarea.value.slice(textarea.selectionStart, textarea.selectionEnd));
  expect(selected).toBe("??? unsupported syntax");
  await expect(page.locator("#markdown-source")).toBeFocused();
  await page.reload();
  await expect(page.locator("#markdown-source")).toHaveValue(invalid);
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
});

test("a delayed parse cannot restore a graph after the source changes", async ({ page }) => {
  await page.goto("/");
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let intercepted!: () => void;
  const ready = new Promise<void>(resolve => { intercepted = resolve; });
  let finished!: () => void;
  const delivered = new Promise<void>(resolve => { finished = resolve; });
  await page.route("**/sync", async route => {
    const response = await route.fetch();
    intercepted();
    await gate;
    await route.fulfill({ response }).catch(() => {}); // The browser may have aborted it.
    finished();
  });
  await page.getByRole("button", { name: "Parse Markdown" }).click();
  await ready;
  await page.locator("#markdown-source").fill("# New\nNarrator: Different snapshot.");
  release();
  await delivered;
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await expect(page.locator("#parse-status")).toHaveText("Edited — parse again");
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Parse Markdown" })).toBeEnabled();
});
