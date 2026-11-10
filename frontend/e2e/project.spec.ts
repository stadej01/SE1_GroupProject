import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

const markdown = `<!-- start: Node_Greeting -->
# Node_Greeting
<!-- category: shop, color: blue -->
Merchant: Welcome, traveler.
* "Browse the shop" -> Node_Shop

# Node_Shop
Merchant: Take your time.
<<jump: Node_Greeting>>
`;

async function register(page: Page) {
  const email = `project-${randomUUID()}@example.com`;
  const password = "Project-browser-42!";
  await page.goto("/");
  await page.getByRole("link", { name: "Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Display name").fill("Browser tester");
  await page.getByLabel("Password:", { exact: true }).fill(password);
  await page.getByLabel("Password confirmation").fill(password);
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your projects", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Browser tester's team", exact: true })).toBeVisible();
  return { email, password };
}

async function createProject(page: Page) {
  const name = `Browser project ${randomUUID()}`;
  await page.getByLabel("Project name").fill(name);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await expect(page.locator("#markdown-source")).toBeEnabled();
  await expect(page.locator("#markdown-source")).toHaveValue("");
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  return { name, url: page.url() };
}

async function parse(page: Page) {
  await page.locator("#markdown-source").fill(markdown);
  await page.getByRole("button", { name: "Parse Markdown" }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(2);
  await expect(page.locator(".react-flow__edge")).toHaveCount(2);
}

async function save(page: Page) {
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.locator("#save-status")).toHaveText("Saved");
}

async function positions(page: Page) {
  // Node transforms use graph coordinates, independent of the viewport zoom.
  return page.locator(".react-flow__node").evaluateAll(nodes =>
    Object.fromEntries(nodes.map(node => {
      const transform = new DOMMatrixReadOnly((node as HTMLElement).style.transform);
      return [node.getAttribute("data-id"), { x: transform.m41, y: transform.m42 }];
    })));
}

async function dragNode(page: Page) {
  const before = await positions(page);
  const heading = page.locator('.react-flow__node[data-id="Node_Greeting"] .dlg-node__heading');
  const box = await heading.boundingBox();
  expect(box).not.toBeNull();
  const x = box!.x + box!.width / 2;
  const y = box!.y + box!.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + 80, y + 65, { steps: 12 });
  await page.mouse.up();
  await expect(page.locator("#save-status")).toHaveText("Unsaved changes");
  const after = await positions(page);
  expect(after.Node_Greeting).not.toEqual(before.Node_Greeting);
  return after;
}

const backLink = (page: Page) => page.getByRole("link", { name: "← Projects", exact: true });
const leaveDialog = (page: Page) => page.getByRole("dialog", { name: "Save your changes before leaving?" });
const leaveButton = (page: Page, name: string) => leaveDialog(page).getByRole("button", { name, exact: true });

async function expectHome(page: Page) {
  await expect(page.getByRole("heading", { name: "Your projects", exact: true })).toBeVisible();
}

async function reopen(page: Page, url: string) {
  await page.goto(url);
  await expect(page.locator("#markdown-source")).toBeEnabled();
}

function recordDialogs(page: Page) {
  const dialogs: string[] = [];
  page.on("dialog", async dialog => { dialogs.push(dialog.type()); await dialog.dismiss(); });
  return dialogs;
}

async function savedProjectWithEdit(page: Page) {
  await register(page);
  const project = await createProject(page);
  await parse(page);
  await save(page);
  const edited = markdown.replace("Welcome, traveler.", "An unsaved greeting.");
  await page.locator("#markdown-source").fill(edited);
  await expect(page.locator("#save-status")).toHaveText("Unsaved changes");
  return { ...project, edited };
}

test("the divider resizes the panels, remembers the width, and resets on double-click", async ({ page }) => {
  await register(page);
  await createProject(page);
  const markdownPanel = page.locator(".source-panel");
  const width = async () => (await markdownPanel.boundingBox())!.width;
  const divider = page.getByRole("separator", { name: "Resize Markdown and graph panels" });
  const startWidth = await width();
  const box = (await divider.boundingBox())!;
  await page.mouse.move(box.x, box.y + 200);
  await page.mouse.down();
  await page.mouse.move(box.x + 220, box.y + 320, { steps: 10 });
  await page.mouse.up();
  const dragged = await width();
  expect(Math.abs(dragged - (startWidth + 220))).toBeLessThanOrEqual(1);

  await page.reload();
  await expect(page.locator("#markdown-source")).toBeEnabled();
  expect(await width()).toBe(dragged);

  await divider.dblclick();
  expect(Math.abs(await width() - startWidth)).toBeLessThanOrEqual(1);
  await page.reload();
  await expect(page.locator("#markdown-source")).toBeEnabled();
  expect(Math.abs(await width() - startWidth)).toBeLessThanOrEqual(1);

  await divider.focus();
  await page.keyboard.press("Home");
  expect(await width()).toBe(280);
  await page.keyboard.press("ArrowRight");
  expect(await width()).toBe(304);
  await page.keyboard.press("Shift+ArrowLeft");
  expect(await width()).toBe(280);
  await page.keyboard.press("End");
  expect((await page.locator(".graph-panel").boundingBox())!.width).toBeGreaterThanOrEqual(420);
});

test("Connections adds and deletes a link, and only one toolbar panel stays open", async ({ page }) => {
  await register(page);
  await createProject(page);
  await parse(page);
  const connections = page.locator("#connections-summary");
  await expect(connections).toHaveText("Connections (2)");
  await expect(page.locator("#connection-from")).toBeHidden();

  await connections.click();
  await page.locator("#connection-from").fill("Node_Greeting");
  await page.locator("#connection-to").fill("Node_Shop");
  await page.locator("#connection-kind").selectOption("jump");
  await page.getByRole("button", { name: "+ Connect nodes", exact: true }).click();
  await expect(page.locator(".react-flow__edge")).toHaveCount(3);
  await expect(connections).toHaveText("Connections (3)");

  await page.locator("#connection-delete").selectOption({ label: "Node_Greeting → Node_Shop (jump)" });
  await page.getByRole("button", { name: "Delete connection", exact: true }).click();
  await expect(page.locator(".react-flow__edge")).toHaveCount(2);
  await expect(connections).toHaveText("Connections (2)");

  await page.locator("#view-summary").click();
  await expect(page.locator("#graph-layout")).toBeVisible();
  await expect(page.locator("#connection-from")).toBeHidden();
  await page.locator("#starting-node-summary").click();
  await expect(page.locator("#starting-node-list")).toBeVisible();
  await expect(page.locator("#graph-layout")).toBeHidden();
  await page.keyboard.press("Escape");
  await expect(page.locator("#starting-node-list")).toBeHidden();
  await connections.click();
  await expect(page.locator("#connection-from")).toBeVisible();
  await page.locator(".react-flow__pane").click({ position: { x: 20, y: 20 } });
  await expect(page.locator("#connection-from")).toBeHidden();
});

test("selecting a node or connection marks its Markdown, and key presses leave the text alone", async ({ page }) => {
  await register(page);
  await createProject(page);
  await parse(page);
  await save(page);
  const source = page.locator("#markdown-source");
  const mark = page.locator("#source-line-mark");
  const pressKeys = async () => {
    for (const key of ["x", "Space", "Enter", "Backspace", "Delete", "ArrowRight"]) await page.keyboard.press(key);
  };
  const expectTextUntouched = async () => {
    await expect(source).toHaveValue(markdown);
    await expect(source).not.toBeFocused();
    await expect(page.locator("#save-status")).not.toHaveText("Unsaved changes");
    await expect(page.locator(".react-flow__node")).toHaveCount(2);
  };

  const before = await positions(page);
  await page.locator('.react-flow__node[data-id="Node_Greeting"]').click();
  await expect(page.locator("#source-selection")).toHaveText("Lines 2–6 · Node_Greeting");
  const area = (await source.boundingBox())!;
  const marked = (await mark.boundingBox())!;
  expect(marked.y - area.y).toBe(18 + 23);
  expect(marked.height).toBe(5 * 23);
  await pressKeys();
  await expectTextUntouched();
  await expect(mark).toBeVisible();
  expect(await positions(page)).toEqual(before);

  await page.locator(".react-flow__pane").click({ position: { x: 20, y: 20 } });
  await expect(mark).toBeHidden();

  const edge = (await page.locator(".react-flow__edge-interaction").first().boundingBox())!;
  await page.mouse.click(edge.x + edge.width / 2, edge.y + edge.height / 2);
  await expect(page.locator("#parse-status")).toContainText("Selected connection");
  await expect(mark).toBeVisible();
  await pressKeys();
  await expectTextUntouched();

  await source.click();
  await expect(mark).toBeHidden();
  await page.keyboard.press("ControlOrMeta+End");
  await page.keyboard.type("Z");
  await expect(source).toHaveValue(markdown + "Z");
  await expect(page.locator("#parse-status")).toHaveText("Edited — parse again");
  await expect(page.locator("#save-status")).toHaveText("Unsaved changes");
});

test("the node details close on an empty click or ×, but keep unapplied changes open", async ({ page }) => {
  await register(page);
  await createProject(page);
  await parse(page);
  await expect(page.locator("#parse-button")).toHaveText("Parse");
  const details = page.locator(".node-edit-panel");
  const node = page.locator('.react-flow__node[data-id="Node_Greeting"]');
  const emptyCanvas = page.locator(".react-flow__pane");
  const speaker = details.getByLabel("Speaker (required)");
  const clickEmptyCanvas = () => emptyCanvas.click({ position: { x: 20, y: 20 } });

  await node.click();
  await expect(details).toBeVisible();
  await clickEmptyCanvas();
  await expect(details).toBeHidden();

  await node.click();
  await details.getByRole("button", { name: "Close node details", exact: true }).click();
  await expect(details).toBeHidden();

  await node.click();
  const canvas = (await emptyCanvas.boundingBox())!;
  await page.mouse.move(canvas.x + 30, canvas.y + 30);
  await page.mouse.down();
  await page.mouse.move(canvas.x + 90, canvas.y + 70, { steps: 6 });
  await page.mouse.up();
  await expect(details).toBeVisible();

  await speaker.fill("Innkeeper");
  await clickEmptyCanvas();
  await expect(details).toBeVisible();
  await expect(details.getByRole("alert")).toContainText("not applied");
  await expect(speaker).toHaveValue("Innkeeper");

  await details.getByRole("button", { name: "Apply to Markdown", exact: true }).click();
  await expect(page.locator("#parse-status")).toContainText("Node edited");
  await expect(details.getByRole("alert")).toHaveText("");
  await clickEmptyCanvas();
  await expect(details).toBeHidden();

  await node.click();
  await speaker.fill("Discard me");
  await details.getByRole("button", { name: "Close node details", exact: true }).click();
  await expect(details).toBeHidden();
  await node.click();
  await expect(speaker).toHaveValue("Innkeeper");
});

test("clicking another node keeps unapplied changes and switches once there are none", async ({ page }) => {
  await register(page);
  await createProject(page);
  await parse(page);
  const details = page.locator(".node-edit-panel");
  const hint = details.getByRole("alert");
  const nodeId = details.getByLabel("Node ID");
  const speaker = details.getByLabel("Speaker (required)");
  const greeting = page.locator('.react-flow__node[data-id="Node_Greeting"]');
  const shop = page.locator('.react-flow__node[data-id="Node_Shop"]');

  await shop.click();
  await expect(nodeId).toHaveValue("Node_Shop");
  await greeting.click();
  await expect(nodeId).toHaveValue("Node_Greeting");
  await details.getByRole("button", { name: "Close node details", exact: true }).click();

  await shop.click();
  await speaker.fill("Innkeeper");
  await greeting.click();
  await expect(nodeId).toHaveValue("Node_Shop");
  await expect(speaker).toHaveValue("Innkeeper");
  await expect(hint).toContainText("not applied");

  await details.getByRole("button", { name: "Apply to Markdown", exact: true }).click();
  await expect(page.locator("#parse-status")).toContainText("Node edited");
  await expect(hint).toHaveText("");
  await greeting.click();
  await expect(nodeId).toHaveValue("Node_Greeting");
  await expect(hint).toHaveText("");

  await speaker.fill("Discard me");
  await greeting.click();
  await expect(speaker).toHaveValue("Discard me");
  await expect(hint).toContainText("not applied");
  await details.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(details).toBeHidden();
  await greeting.click();
  await expect(speaker).toHaveValue("Merchant");
  await expect(hint).toHaveText("");
});

test("the highlight stays on the node being edited, and dragging moves only the dragged node", async ({ page }) => {
  await register(page);
  await createProject(page);
  await parse(page);
  const yellow = "rgb(245, 184, 0)";
  const plain = "rgb(212, 212, 216)";
  const details = page.locator(".node-edit-panel");
  const greeting = page.locator('.react-flow__node[data-id="Node_Greeting"]');
  const shop = page.locator('.react-flow__node[data-id="Node_Shop"]');
  const expectHighlight = async (on: typeof greeting, off: typeof greeting) => {
    await expect(on.locator(".dlg-node")).toHaveCSS("border-top-color", yellow);
    await expect(off.locator(".dlg-node")).toHaveCSS("border-top-color", plain);
  };

  await shop.click();
  await expectHighlight(shop, greeting);
  await details.getByLabel("Speaker (required)").fill("Innkeeper");

  await greeting.click();
  await expectHighlight(shop, greeting);
  await page.locator(".react-flow__pane").click({ position: { x: 20, y: 20 } });
  await expectHighlight(shop, greeting);

  const before = await positions(page);
  const box = (await greeting.locator(".dlg-node__heading").boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 40, box.y + box.height / 2 + 60, { steps: 8 });
  await page.mouse.up();
  const after = await positions(page);
  expect(after.Node_Greeting).not.toEqual(before.Node_Greeting);
  expect(after.Node_Shop).toEqual(before.Node_Shop);
  await expectHighlight(shop, greeting);

  await details.getByRole("button", { name: "Apply to Markdown", exact: true }).click();
  await expect(page.locator("#parse-status")).toContainText("Node edited");
  await expectHighlight(shop, greeting);
  await greeting.click();
  await expectHighlight(greeting, shop);
});

test("a node keeps its color stripe when selected and deselected", async ({ page }) => {
  await register(page);
  await createProject(page);
  await parse(page);
  const blue = "rgb(61, 90, 128)";
  const node = page.locator('.react-flow__node[data-id="Node_Greeting"]');
  const card = node.locator(".dlg-node");
  await expect(card).toHaveCSS("border-left-color", blue);

  await node.click();
  await expect(card).toHaveCSS("border-top-color", "rgb(245, 184, 0)");
  await expect(card).toHaveCSS("border-left-color", blue);

  await page.locator(".react-flow__pane").click({ position: { x: 20, y: 20 } });
  await expect(card).toHaveCSS("border-top-color", "rgb(212, 212, 216)");
  await expect(card).toHaveCSS("border-left-color", blue);
});

test("← Projects goes straight home when nothing is unsaved", async ({ page }) => {
  const dialogs = recordDialogs(page);
  await register(page);
  await createProject(page);
  await parse(page);
  await save(page);
  await backLink(page).click();
  await expectHome(page);
  expect(dialogs).toEqual([]);
});

test("Cancel and Escape stay on the project with the edit and focus intact", async ({ page }) => {
  const dialogs = recordDialogs(page);
  const { edited } = await savedProjectWithEdit(page);
  await backLink(page).click();
  await expect(leaveDialog(page)).toBeVisible();
  await leaveButton(page, "Cancel").click();
  await expect(leaveDialog(page)).toBeHidden();
  await expect(backLink(page)).toBeFocused();

  await backLink(page).click();
  await expect(leaveDialog(page)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(leaveDialog(page)).toBeHidden();
  await expect(backLink(page)).toBeFocused();

  expect(page.url()).toContain("/projects/");
  await expect(page.locator("#markdown-source")).toHaveValue(edited);
  await expect(page.locator("#save-status")).toHaveText("Unsaved changes");
  expect(dialogs).toEqual([]);
});

test("Discard changes goes home without a browser prompt and drops the edit", async ({ page }) => {
  const dialogs = recordDialogs(page);
  const { url } = await savedProjectWithEdit(page);
  await backLink(page).click();
  await leaveButton(page, "Discard changes").click();
  await expectHome(page);
  expect(dialogs).toEqual([]);
  await reopen(page, url);
  await expect(page.locator("#markdown-source")).toHaveValue(markdown);
});

test("Save and leave stores text, positions, and graph edits without parsing again", async ({ page }) => {
  const dialogs = recordDialogs(page);
  await register(page);
  const { url } = await createProject(page);
  await parse(page);
  await save(page);
  const moved = await dragNode(page);
  await page.locator("#connections-summary").click();
  await page.locator("#connection-from").fill("Node_Greeting");
  await page.locator("#connection-to").fill("Node_Shop");
  await page.locator("#connection-kind").selectOption("jump");
  await page.getByRole("button", { name: "+ Connect nodes", exact: true }).click();
  await expect(page.locator(".react-flow__edge")).toHaveCount(3);
  expect(await page.locator("#markdown-source").inputValue()).toBe(markdown);

  const parses: string[] = [];
  page.on("request", request => { if (request.url().endsWith("/sync")) parses.push(request.url()); });
  await backLink(page).click();
  await leaveButton(page, "Save and leave").click();
  await expectHome(page);
  expect(dialogs).toEqual([]);
  expect(parses).toEqual([]);

  await reopen(page, url);
  await expect(page.locator(".react-flow__edge")).toHaveCount(3);
  expect(await page.locator("#markdown-source").inputValue()).toContain("<<jump: Node_Shop>>");
  await expect.poll(() => positions(page)).toEqual(moved);
});

test("the dialog locks while saving, including Escape", async ({ page }) => {
  await savedProjectWithEdit(page);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/save", async route => { await gate; await route.continue(); });
  await backLink(page).click();
  await leaveButton(page, "Save and leave").click();
  for (const name of ["Save and leave", "Discard changes", "Cancel"]) {
    await expect(leaveButton(page, name)).toBeDisabled();
  }
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await expect(leaveDialog(page)).toBeVisible();
  release();
  await expectHome(page);
});

test("Save and leave shows a stale save and keeps the text on the page", async ({ page, context }) => {
  const { url, edited } = await savedProjectWithEdit(page);
  const other = await context.newPage();
  await reopen(other, url);
  await other.locator("#markdown-source").fill(markdown.replace("Welcome, traveler.", "Saved elsewhere."));
  await save(other);
  await other.close();

  await backLink(page).click();
  await leaveButton(page, "Save and leave").click();
  await expect(leaveDialog(page)).toBeHidden();
  await expect(page.locator("#save-status")).toContainText("A newer version was saved");
  await expect(page.locator("#markdown-source")).toHaveValue(edited);
  expect(page.url()).toBe(url);
  await expect(page.getByRole("button", { name: "Save", exact: true })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeEnabled();
});

test("a modified click on ← Projects opens a new tab and leaves the page alone", async ({ page, context }) => {
  const { url, edited } = await savedProjectWithEdit(page);
  const opened = context.waitForEvent("page");
  await backLink(page).click({ modifiers: ["ControlOrMeta"] });
  const home = await opened;
  await expectHome(home);
  await home.close();
  await expect(leaveDialog(page)).toBeHidden();
  expect(page.url()).toBe(url);
  await expect(page.locator("#markdown-source")).toHaveValue(edited);
});

test("register, create, parse, drag, save, and reload a project without dialogs", async ({ page }) => {
  const dialogs: string[] = [];
  const errors: string[] = [];
  page.on("dialog", async dialog => { dialogs.push(dialog.type()); await dialog.dismiss(); });
  page.on("pageerror", error => errors.push(error.message));
  await register(page);
  await createProject(page);
  await parse(page);
  const moved = await dragNode(page);
  await save(page);
  await page.reload();
  await expect(page.locator("#markdown-source")).toHaveValue(markdown);
  await expect(page.locator(".react-flow__node")).toHaveCount(2);
  await expect(page.locator(".react-flow__edge")).toHaveCount(2);
  await expect.poll(() => positions(page)).toEqual(moved);
  await expect(page.locator("#save-status")).toHaveText("No unsaved changes");
  expect(dialogs).toEqual([]);
  expect(errors).toEqual([]);
});

test("rejects a stale save and keeps the second page's text", async ({ page, context }) => {
  await register(page);
  const project = await createProject(page);
  await parse(page);
  await save(page);
  const second = await context.newPage();
  await second.goto(project.url);
  await expect(second.locator("#markdown-source")).toHaveValue(markdown);
  const firstEdit = markdown.replace("Welcome, traveler.", "Saved by the first page.");
  const secondEdit = markdown.replace("Welcome, traveler.", "Keep the second page's edits.");
  await page.locator("#markdown-source").fill(firstEdit);
  await second.locator("#markdown-source").fill(secondEdit);
  await save(page);
  const rejected = second.waitForResponse(response =>
    response.url().endsWith("/save") && response.request().method() === "PUT");
  await second.getByRole("button", { name: "Save", exact: true }).click();
  expect((await rejected).status()).toBe(409);
  await expect(second.locator("#save-status")).toHaveText(
    "A newer version was saved (revision 3). Your text is still here. Copy it, then reload.");
  await expect(second.locator("#markdown-source")).toHaveValue(secondEdit);
  await page.reload();
  await expect(page.locator("#markdown-source")).toHaveValue(firstEdit);
});

test("returns to the requested project after login and hides it from another account", async ({ page, browser, baseURL }) => {
  const account = await register(page);
  const project = await createProject(page);
  const guest = await browser.newContext({ baseURL });
  try {
    const visitor = await guest.newPage();
    await visitor.goto(project.url);
    await expect(visitor).toHaveURL(/\/login\/\?next=/);
    expect(new URL(visitor.url()).searchParams.get("next")).toBe(new URL(project.url).pathname);
    await visitor.getByRole("button", { name: "Log in", exact: true }).click();
    await expect(visitor.locator("#email-error")).toHaveText("This field may not be blank.");
    await visitor.getByLabel("Email:", { exact: true }).fill(account.email);
    await visitor.getByLabel("Password:", { exact: true }).fill("not-the-password");
    await visitor.getByRole("button", { name: "Log in", exact: true }).click();
    await expect(visitor.getByRole("alert")).toHaveText("Invalid email or password.");
    await visitor.getByLabel("Password:", { exact: true }).fill(account.password);
    await visitor.getByRole("button", { name: "Log in", exact: true }).click();
    await expect(visitor).toHaveURL(project.url);
    await expect(visitor.getByRole("heading", { name: project.name, exact: true })).toBeVisible();
    await visitor.getByRole("button", { name: "Log out", exact: true }).click();
    await register(visitor);
    const denied = await visitor.goto(project.url);
    expect(denied!.status()).toBe(403);
    await expect(visitor.getByRole("heading", { name: "Access denied", exact: true })).toBeVisible();
    await expect(visitor.locator("body")).toContainText("You are not a member of this project's team.");
    await expect(visitor.locator("#markdown-source")).toHaveCount(0);
    expect(await visitor.content()).not.toContain(project.name);
  } finally {
    await guest.close();
  }
});

test("a save after the sign-in cookie is gone asks to sign in and keeps the text", async ({ page, context }) => {
  const account = await register(page);
  const { url } = await createProject(page);
  await parse(page);
  await save(page);
  const edited = markdown.replace("Welcome, traveler.", "Typed after signing out.");
  await page.locator("#markdown-source").fill(edited);
  await context.clearCookies({ name: "se1_neon_token" });
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.locator("#save-status")).toContainText("You are signed out. Your text is still here.");
  await expect(page.locator("#markdown-source")).toHaveValue(edited);
  expect(page.url()).toBe(url);

  const opened = context.waitForEvent("page");
  await page.getByRole("link", { name: "Sign in in a new tab", exact: true }).click();
  const login = await opened;
  await login.getByLabel("Email:", { exact: true }).fill(account.email);
  await login.getByLabel("Password:", { exact: true }).fill(account.password);
  await login.getByRole("button", { name: "Log in", exact: true }).click();
  await expectHome(login);
  await login.close();
  await save(page);
  await reopen(page, url);
  await expect(page.locator("#markdown-source")).toHaveValue(edited);
});

test("warns on close after only dragging a node and stops warning after saving", async ({ page }) => {
  await register(page);
  await createProject(page);
  await parse(page);
  await save(page);
  await dragNode(page);
  await expect(page.locator("#markdown-source")).toHaveValue(markdown);
  const prompt = page.waitForEvent("dialog");
  await page.close({ runBeforeUnload: true });
  const dialog = await prompt;
  expect(dialog.type()).toBe("beforeunload");
  await dialog.dismiss();
  expect(page.isClosed()).toBe(false);
  await save(page);
  const unexpected: string[] = [];
  page.on("dialog", async next => { unexpected.push(next.type()); await next.accept(); });
  const closed = page.waitForEvent("close");
  await page.close({ runBeforeUnload: true });
  await closed;
  expect(unexpected).toEqual([]);
});
