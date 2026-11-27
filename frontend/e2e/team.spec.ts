import { randomUUID } from "node:crypto";
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

// Each person signs in through their own browser context, so their sessions stay separate.

const markdown = `<!-- start: Node_Greeting -->
# Node_Greeting
Merchant: Welcome, traveler.
* "Browse the shop" -> Node_Shop

# Node_Shop
Merchant: Take your time.
<<jump: Node_Greeting>>
`;

interface Person { context: BrowserContext; page: Page; email: string; name: string }

async function person(browser: Browser, baseURL: string | undefined, label: string): Promise<Person> {
  const context = await browser.newContext({ baseURL });
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: baseURL });
  const page = await context.newPage();
  const id = randomUUID().slice(0, 8);
  const email = `${label.toLowerCase()}-${id}@example.com`;
  const name = `${label} ${id}`;
  const password = "Team-browser-42!";
  await page.goto("/accounts/register/");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Display name").fill(name);
  await page.getByLabel("Password:", { exact: true }).fill(password);
  await page.getByLabel("Password confirmation").fill(password);
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your projects", exact: true })).toBeVisible();
  return { context, page, email, name };
}

async function createTeam(page: Page, name = `Team ${randomUUID().slice(0, 8)}`) {
  await page.getByLabel("Team name").fill(name);
  await page.getByRole("button", { name: "Create team", exact: true }).click();
  await expect(page.getByRole("status")).toContainText(`Created ${name}.`);
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  return name;
}

async function openMembers(page: Page, team: string) {
  await page.getByRole("link", { name: `Manage members of ${team}`, exact: true }).click();
  await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText(team);
}

async function addMember(page: Page, email: string) {
  await page.getByLabel("Email").fill(email);
  await page.getByRole("button", { name: "Add member", exact: true }).click();
}

async function createProject(page: Page, team: string) {
  const name = `Story ${randomUUID().slice(0, 8)}`;
  await page.getByRole("link", { name: "Projects", exact: true }).click();
  await page.getByLabel("Project name").fill(name);
  await expect(page.getByLabel("Team:", { exact: true }).locator("option:checked")).toHaveText(team);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await expect(page.locator("#markdown-source")).toBeEnabled();
  return { name, url: page.url() };
}

async function save(page: Page) {
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.locator("#save-status")).toHaveText("Saved");
}

async function openProject(page: Page, url: string) {
  await page.goto(url);
  await expect(page.locator("#markdown-source")).toBeEnabled();
}

async function sharedTeam(browser: Browser, baseURL: string | undefined) {
  const owner = await person(browser, baseURL, "Owner");
  const mate = await person(browser, baseURL, "Mate");
  const team = await createTeam(owner.page);
  await openMembers(owner.page, team);
  await addMember(owner.page, mate.email);
  await expect(owner.page.getByRole("status")).toContainText(`Added ${mate.name}.`);
  return { owner, mate, team };
}

test("a signed-in user creates a team, and a blank name shows an error", async ({ browser, baseURL }) => {
  const ada = await person(browser, baseURL, "Ada");
  try {
    await ada.page.getByLabel("Team name").fill("   ");
    await ada.page.getByRole("button", { name: "Create team", exact: true }).click();
    await expect(ada.page.getByText("Enter a team name.")).toBeVisible();
    await expect(ada.page.getByLabel("Team name")).toBeFocused();
    await expect(ada.page.getByLabel("Team name")).toHaveAccessibleDescription("Enter a team name.");
    const team = await createTeam(ada.page);
    await expect(ada.page.getByLabel("Team:", { exact: true }).locator("option:checked")).toHaveText(team);
    expect(new URL(ada.page.url()).hash).toMatch(/^#team-\d+$/);
    await expect(ada.page.getByRole("link", { name: `Manage members of ${team}` })).toHaveText("Manage members");
    await openMembers(ada.page, team);
    await expect(ada.page.getByRole("heading", { name: "Members (1)" })).toBeVisible();
    await expect(ada.page.locator(".members li")).toHaveCount(1);
    await expect(ada.page.locator(".members li")).toContainText(ada.email);
    await expect(ada.page.locator(".members li .you")).toHaveText("You");
  } finally {
    await ada.context.close();
  }
});

test("a shared team opens the same project for both members and keeps its context on return", async ({ browser, baseURL }) => {
  const owner = await person(browser, baseURL, "Owner");
  const mate = await person(browser, baseURL, "Mate");
  try {
    await openMembers(owner.page, `${owner.name}'s team`);
    await addMember(owner.page, mate.email);
    await owner.page.getByRole("link", { name: "Projects", exact: true }).click();
    const team = await createTeam(owner.page);
    await openMembers(owner.page, team);
    await addMember(owner.page, `nobody-${randomUUID()}@example.com`);
    await expect(owner.page.getByText("No account uses this email.")).toBeVisible();
    await expect(owner.page.getByLabel("Email")).toBeFocused();
    await expect(owner.page.getByLabel("Email")).toHaveAccessibleDescription(/No account uses this email/);
    await owner.page.getByRole("button", { name: "Copy sign-up link" }).click();
    expect(await owner.page.evaluate(() => navigator.clipboard.readText())).toBe(new URL("/accounts/register/", baseURL).href);
    await owner.page.getByRole("button", { name: `${mate.name} ${mate.email}` }).click();
    await expect(owner.page.getByLabel("Registered email")).toHaveValue(mate.email);
    await expect(owner.page.getByRole("heading", { name: "Members (1)" })).toBeVisible();
    await owner.page.getByRole("button", { name: "Add member", exact: true }).click();
    await expect(owner.page.getByRole("region", { name: "Members (2)" }).getByRole("status"))
      .toHaveText(`Added ${mate.name}.`);
    await expect(owner.page.getByRole("region", { name: "From your other teams" })).toBeHidden();
    await addMember(owner.page, mate.email.toUpperCase());
    await expect(owner.page.getByText(`${mate.name} is already a member of this team.`)).toBeVisible();
    await expect(owner.page.locator(".members li")).toHaveCount(2);

    const project = await createProject(owner.page, team);
    await mate.page.reload();
    await expect(mate.page.getByRole("heading", { name: team, exact: true })).toBeVisible();
    await expect(mate.page.getByRole("link", { name: project.name, exact: true })).toBeVisible();
    await openMembers(mate.page, team);
    await expect(mate.page.locator(".members li")).toHaveCount(2);
    await expect(mate.page.locator(".members li", { hasText: mate.email }).locator(".you")).toHaveText("You");

    await expect(owner.page.locator("#project-team")).toHaveText(`Team: ${team}`);
    await expect(owner.page.locator("#current-user")).toHaveText(`Signed in as ${owner.name}`);
    await owner.page.getByRole("link", { name: "← Projects", exact: true }).click();
    expect(new URL(owner.page.url()).hash).toMatch(/^#team-\d+$/);
    await expect(owner.page.locator(":target h2")).toHaveText(team);
    await expect(owner.page.getByLabel("Team:", { exact: true }).locator("option:checked")).toHaveText(team);
    await openProject(mate.page, project.url);
    await expect(mate.page.locator("#current-user")).toHaveText(`Signed in as ${mate.name}`);
  } finally {
    await owner.context.close();
    await mate.context.close();
  }
});

test("a removed member loses the team, gets 403, and an open editor keeps its text", async ({ browser, baseURL }) => {
  const { owner, mate, team } = await sharedTeam(browser, baseURL);
  try {
    const project = await createProject(owner.page, team);
    await openProject(mate.page, project.url);
    const source = mate.page.locator("#markdown-source");
    await source.fill(markdown);
    await mate.page.getByRole("button", { name: "Parse Markdown" }).click();
    await mate.page.locator('.react-flow__node[data-id="Node_Shop"]').click();
    await mate.page.getByLabel("Dialogue (one line per paragraph)").fill("Keep my graph edit.");
    await mate.page.getByRole("button", { name: "Apply to Markdown", exact: true }).click();
    await expect(source).toHaveValue(markdown);

    await owner.page.goto("/");
    await openMembers(owner.page, team);
    await owner.page.getByRole("button", { name: `Remove ${mate.name}`, exact: true }).click();
    const dialog = owner.page.getByRole("dialog", { name: `Remove ${mate.name}?` });
    await expect(dialog).toContainText(`${mate.email} will lose access to ${team} and its 1 project.`);
    await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
    await expect(owner.page.locator(".members li")).toHaveCount(2);
    await owner.page.getByRole("button", { name: `Remove ${mate.name}`, exact: true }).click();
    await dialog.getByRole("button", { name: "Remove member", exact: true }).click();
    await expect(owner.page.getByRole("status")).toContainText(`Removed ${mate.name}.`);
    await expect(owner.page.locator(".members li")).toHaveCount(1);

    await mate.page.getByRole("button", { name: "Save", exact: true }).click();
    const recovery = mate.page.getByRole("region", { name: "Project access" });
    await expect(recovery).toContainText("You no longer have access");
    await expect(mate.page.getByRole("button", { name: "Save", exact: true })).toBeDisabled();
    await expect(recovery.getByRole("button", { name: "Load latest version" })).toBeHidden();
    await recovery.getByRole("button", { name: "Copy my Markdown" }).click();
    expect(await mate.page.evaluate(() => navigator.clipboard.readText()))
      .toContain("Merchant: Keep my graph edit.");
    const back = mate.page.getByRole("link", { name: "← Projects" });
    await back.click();
    await mate.page.getByRole("button", { name: "Stay here" }).click();
    await expect(source).toHaveValue(markdown);

    await back.click();
    await mate.page.getByRole("button", { name: "Leave editor" }).click();
    await expect(mate.page.getByRole("heading", { name: "Your projects" })).toBeVisible();
    const other = mate.page;
    await expect(other.getByRole("heading", { name: team, exact: true })).toHaveCount(0);
    expect((await other.goto(project.url))!.status()).toBe(403);
    expect((await other.request.get(project.url.replace("/projects/", "/api/v1/projects/").replace(/\/$/, ""))).status()).toBe(403);
    const teamPage = await other.goto(owner.page.url());
    expect(teamPage!.status()).toBe(403);
    await expect(other.getByText("You are not a member of this team.")).toBeVisible();
  } finally {
    await owner.context.close();
    await mate.context.close();
  }
});

test("a member leaves, and the last member cannot leave", async ({ browser, baseURL }) => {
  const { owner, mate, team } = await sharedTeam(browser, baseURL);
  try {
    await mate.page.reload();
    await openMembers(mate.page, team);
    await mate.page.getByRole("button", { name: "Leave team", exact: true }).click();
    const dialog = mate.page.getByRole("dialog", { name: `Leave ${team}?` });
    await dialog.getByRole("button", { name: "Leave team", exact: true }).click();
    await expect(mate.page.getByRole("status")).toContainText(`You left ${team}.`);
    await expect(mate.page.getByRole("heading", { name: team, exact: true })).toHaveCount(0);

    await owner.page.reload();
    const leave = owner.page.getByRole("button", { name: "Leave team", exact: true });
    await expect(leave).toBeDisabled();
    await expect(leave).toHaveAccessibleDescription("A team needs at least one member.");
    const forced = await owner.page.request.post(owner.page.url().replace(/\/$/, "/leave/"), {
      headers: { "X-CSRFToken": (await owner.context.cookies()).find(c => c.name === "se1_neon_csrftoken")!.value },
    });
    expect(forced.status()).toBe(409);
    await owner.page.reload();
    await expect(owner.page.locator(".members li")).toHaveCount(1);
  } finally {
    await owner.context.close();
    await mate.context.close();
  }
});

test("a signed-in nonmember gets 403 for the team page and member changes", async ({ browser, baseURL }) => {
  const { owner, mate, team } = await sharedTeam(browser, baseURL);
  const outsider = await person(browser, baseURL, "Outsider");
  try {
    const teamUrl = owner.page.url();
    const page = await outsider.page.goto(teamUrl);
    expect(page!.status()).toBe(403);
    await expect(outsider.page.getByText("You are not a member of this team.")).toBeVisible();
    expect(await outsider.page.content()).not.toContain(owner.email);
    const csrf = (await outsider.context.cookies()).find(c => c.name === "se1_neon_csrftoken")!.value;
    const add = await outsider.page.request.post(`${teamUrl}members/`, {
      form: { email: outsider.email }, headers: { "X-CSRFToken": csrf },
    });
    expect(add.status()).toBe(403);
    await owner.page.reload();
    await expect(owner.page.locator(".members li")).toHaveCount(2);
    await expect(owner.page.locator(".members")).not.toContainText(outsider.email);
    await expect(owner.page.locator(".members")).toContainText(mate.email);
    await expect(owner.page.getByRole("navigation", { name: "Breadcrumb" })).toContainText(team);
  } finally {
    await owner.context.close();
    await mate.context.close();
    await outsider.context.close();
  }
});

test("after a 409, a member copies unsaved Markdown with graph edits and loads the latest version", async ({ browser, baseURL }) => {
  const { owner, mate, team } = await sharedTeam(browser, baseURL);
  try {
    const project = await createProject(owner.page, team);
    await owner.page.locator("#markdown-source").fill(markdown);
    await owner.page.getByRole("button", { name: "Parse Markdown" }).click();
    await expect(owner.page.locator(".react-flow__node")).toHaveCount(2);
    await save(owner.page);

    await openProject(mate.page, project.url);
    await expect(mate.page.locator(".react-flow__node")).toHaveCount(2);
    const ownerEdit = markdown.replace("Welcome, traveler.", "Saved by the owner.");
    await owner.page.locator("#markdown-source").fill(ownerEdit);
    await save(owner.page);

    // The mate applies a graph edit that has not reached the Markdown box yet.
    await mate.page.locator('.react-flow__node[data-id="Node_Shop"]').click();
    await mate.page.getByLabel("Dialogue (one line per paragraph)").fill("Edited in the graph.");
    await mate.page.getByRole("button", { name: "Apply to Markdown", exact: true }).click();
    await expect(mate.page.locator("#save-status")).toHaveText("Unsaved changes");
    const sourceBefore = await mate.page.locator("#markdown-source").inputValue();
    expect(sourceBefore).not.toContain("Edited in the graph.");

    await mate.page.getByRole("button", { name: "Save", exact: true }).click();
    await expect(mate.page.locator("#conflict-message")).toContainText("A newer version was saved (revision 3).");
    await expect(mate.page.locator("#markdown-source")).toHaveValue(sourceBefore);
    await expect(mate.page.locator(".react-flow__node")).toHaveCount(2);

    await mate.page.getByRole("button", { name: "Copy my Markdown", exact: true }).click();
    await expect(mate.page.locator("#conflict-feedback")).toHaveText("Copied your Markdown.");
    const copied = await mate.page.evaluate(() => navigator.clipboard.readText());
    expect(copied).toContain("Edited in the graph.");
    expect(copied).toContain("Welcome, traveler.");

    const load = mate.page.getByRole("button", { name: "Load latest version", exact: true });
    const confirm = mate.page.getByRole("dialog", { name: "Load the latest version?" });
    await load.click();
    await expect(confirm).toContainText("Your unsaved Markdown and node positions will be replaced");
    await confirm.getByRole("button", { name: "Cancel", exact: true }).click();
    await expect(mate.page.locator("#markdown-source")).toHaveValue(sourceBefore);

    await load.click();
    await confirm.getByRole("button", { name: "Load latest version", exact: true }).click();
    await expect(mate.page.locator("#markdown-source")).toHaveValue(ownerEdit);
    await expect(mate.page.locator("#save-status")).toHaveText("Loaded the latest version (revision 3)");
    await expect(load).toBeHidden();
    await expect(mate.page.locator(".react-flow__node")).toHaveCount(2);

    const mateEdit = ownerEdit.replace("Take your time.", "Saved by the mate after loading.");
    await mate.page.locator("#markdown-source").fill(mateEdit);
    await save(mate.page);
    await owner.page.reload();
    await expect(owner.page.locator("#markdown-source")).toHaveValue(mateEdit);
  } finally {
    await owner.context.close();
    await mate.context.close();
  }
});

test("loading the latest version locks editing, and a failed load keeps the text", async ({ browser, baseURL }) => {
  const { owner, mate, team } = await sharedTeam(browser, baseURL);
  try {
    const project = await createProject(owner.page, team);
    await openProject(mate.page, project.url);
    await owner.page.locator("#markdown-source").fill(markdown);
    await save(owner.page);
    const mine = "# Mine\nMate: Keep this.";
    await mate.page.locator("#markdown-source").fill(mine);
    await mate.page.getByRole("button", { name: "Save", exact: true }).click();
    await expect(mate.page.locator("#conflict-message")).toContainText("A newer version was saved");

    // A refused clipboard shows the text to copy by hand.
    await mate.page.evaluate(() => {
      navigator.clipboard.writeText = () => Promise.reject(new Error("denied"));
    });
    await mate.page.getByRole("button", { name: "Copy my Markdown", exact: true }).click();
    const fallback = mate.page.getByLabel("Copying failed. Select this text and copy it.");
    await expect(fallback).toBeVisible();
    await expect(fallback).toHaveValue(mine);
    await expect(fallback).toBeFocused();
    expect(await fallback.evaluate((box: HTMLTextAreaElement) => box.selectionEnd - box.selectionStart)).toBe(mine.length);

    const apiUrl = project.url.replace("/projects/", "/api/v1/projects/").replace(/\/$/, "");
    let release!: () => void;
    const held = new Promise<void>(resolve => { release = resolve; });
    await mate.page.route(apiUrl, async route => { await held; await route.abort(); });
    const load = mate.page.getByRole("button", { name: "Load latest version", exact: true });
    await load.click();
    await mate.page.getByRole("dialog", { name: "Load the latest version?" })
      .getByRole("button", { name: "Load latest version", exact: true }).click();
    await expect(mate.page.locator("#save-status")).toHaveText("Loading the latest version…");
    await expect(mate.page.locator("#markdown-source")).toBeDisabled();
    await expect(mate.page.getByRole("button", { name: "Save", exact: true })).toBeDisabled();
    await expect(load).toBeDisabled();
    release();
    await expect(mate.page.locator("#save-status")).toHaveText("Could not reach the server. Your text is still here. Try again.");
    await expect(mate.page.locator("#markdown-source")).toBeEnabled();
    await expect(mate.page.locator("#markdown-source")).toHaveValue(mine);
    await expect(load).toBeEnabled();

    await mate.page.unroute(apiUrl);
    await load.click();
    await mate.page.getByRole("dialog", { name: "Load the latest version?" })
      .getByRole("button", { name: "Load latest version", exact: true }).click();
    await expect(mate.page.locator("#markdown-source")).toHaveValue(markdown);
    await expect(mate.page.locator("#save-status")).toHaveText("Loaded the latest version (revision 2)");
  } finally {
    await owner.context.close();
    await mate.context.close();
  }
});

test("after loading the latest version, Undo and Delete cannot bring back the stale copy", async ({ browser, baseURL }) => {
  const { owner, mate, team } = await sharedTeam(browser, baseURL);
  try {
    const project = await createProject(owner.page, team);
    await owner.page.locator("#markdown-source").fill(markdown);
    await owner.page.getByRole("button", { name: "Parse Markdown" }).click();
    await expect(owner.page.locator(".react-flow__node")).toHaveCount(2);
    await save(owner.page);
    await openProject(mate.page, project.url);
    await expect(mate.page.locator(".react-flow__node")).toHaveCount(2);
    const ownerEdit = markdown.replace("Welcome, traveler.", "Saved by the owner.");
    await owner.page.locator("#markdown-source").fill(ownerEdit);
    await save(owner.page);

    // The mate deletes a node in the graph, which records an Undo step, then saves a stale copy.
    await mate.page.locator('.react-flow__node[data-id="Node_Shop"]').click();
    await mate.page.getByRole("button", { name: "Close node details" }).click();
    mate.page.once("dialog", dialog => { void dialog.accept(); });
    await mate.page.getByRole("button", { name: /^Delete selected/ }).click();
    await expect(mate.page.locator(".react-flow__node")).toHaveCount(1);
    await mate.page.getByRole("button", { name: "Save", exact: true }).click();
    await expect(mate.page.locator("#conflict-message")).toContainText("A newer version was saved");

    await mate.page.getByRole("button", { name: "Load latest version", exact: true }).click();
    await mate.page.getByRole("dialog", { name: "Load the latest version?" })
      .getByRole("button", { name: "Load latest version", exact: true }).click();
    await expect(mate.page.locator("#markdown-source")).toHaveValue(ownerEdit);
    await expect(mate.page.locator(".react-flow__node")).toHaveCount(2);
    await expect(mate.page.getByRole("button", { name: /^Delete selected/ })).toHaveText("Delete selected");

    await mate.page.locator(".react-flow__pane").click({ position: { x: 12, y: 12 } });
    await mate.page.keyboard.press("ControlOrMeta+z");
    await mate.page.keyboard.press("Delete");
    await expect(mate.page.locator("#markdown-source")).toHaveValue(ownerEdit);
    await expect(mate.page.locator(".react-flow__node")).toHaveCount(2);
    await expect(mate.page.locator("#save-status")).toHaveText("Loaded the latest version (revision 3)");
  } finally {
    await owner.context.close();
    await mate.context.close();
  }
});
