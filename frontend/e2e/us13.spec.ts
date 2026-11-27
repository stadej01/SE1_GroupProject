import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { expect, test, type Page } from "@playwright/test";

// US-13: reviewers comment on nodes without changing the dialogue.

const markdown = `<!-- start: Node_Greeting -->
# Node_Greeting
Merchant: Welcome, traveler.
* "Browse the shop" -> Node_Shop

# Node_Shop
Merchant: Take your time.
<<jump: Node_Greeting>>
`;

async function register(page: Page, displayName: string) {
  const email = `us13-${randomUUID()}@example.com`;
  const password = "Project-browser-42!";
  await page.goto("/");
  await page.getByRole("link", { name: "Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Display name").fill(displayName);
  await page.getByLabel("Password:", { exact: true }).fill(password);
  await page.getByLabel("Password confirmation").fill(password);
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your projects", exact: true })).toBeVisible();
  return email;
}

// The app has no screen for inviting teammates yet; add the membership the way
// the README's admin steps do, in the browser-test database.
function joinTeam(ownerEmail: string, memberEmail: string) {
  const script = [
    "import os",
    "from accounts.models import User",
    "from teams.models import Team, TeamMembership",
    "owner = User.objects.get(email=os.environ['US13_OWNER'])",
    "member = User.objects.get(email=os.environ['US13_MEMBER'])",
    "TeamMembership.objects.create(team=Team.objects.get(memberships__user=owner), user=member)",
  ].join("\n");
  execFileSync("python", ["../backend/manage.py", "shell", "--settings=config.settings_e2e", "-c", script], {
    env: { ...process.env, DJANGO_DATABASE_PATH: resolve("../backend/project-browser-tests.sqlite3"),
      US13_OWNER: ownerEmail, US13_MEMBER: memberEmail },
    stdio: "pipe",
  });
}

async function openNode(page: Page, nodeId: string) {
  await page.locator(`.react-flow__node[data-id="${nodeId}"]`).click();
  const details = page.locator(".node-edit-panel");
  await expect(details).toBeVisible();
  return details.locator("#node-comments");
}

test("reviewers comment on nodes without changing or exporting the dialogue", async ({ page: reviewer, browser }) => {
  // AC1: reviewer A comments on a saved node.
  const reviewerEmail = await register(reviewer, "Reviewer A");
  await reviewer.getByLabel("Project name").fill(`Comments ${randomUUID()}`);
  await reviewer.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(reviewer.locator("#markdown-source")).toBeEnabled();
  await reviewer.locator("#markdown-source").fill(markdown);
  await reviewer.getByRole("button", { name: "Parse Markdown" }).click();
  await expect(reviewer.locator(".react-flow__node")).toHaveCount(2);
  await reviewer.getByRole("button", { name: "Save", exact: true }).click();
  await expect(reviewer.locator("#save-status")).toHaveText("Saved");
  const projectUrl = reviewer.url();

  const comments = await openNode(reviewer, "Node_Greeting");
  await expect(comments.getByText("No comments on this node yet.")).toBeVisible();
  await comments.getByLabel("Add a comment").fill("Is the greeting too <b>formal</b>?");
  await comments.getByRole("button", { name: "Add comment", exact: true }).click();
  const own = comments.locator(".node-comment");
  await expect(own).toHaveCount(1);
  await expect(own.locator(".node-comment-body")).toHaveText("Is the greeting too <b>formal</b>?");
  await expect(own.locator("strong")).toHaveText("Reviewer A");
  await expect(comments.getByLabel("Add a comment")).toHaveValue("");
  const firstBadge = reviewer.locator('.react-flow__node[data-id="Node_Greeting"] .dlg-node__comments');
  await expect(firstBadge).toHaveText("1 comment");
  // The icon shows, and only the number is visible; the word is for screen readers.
  await expect(firstBadge.locator("svg")).toBeVisible();
  await expect(firstBadge.locator(".visually-hidden")).toHaveText(" comment");
  // Comments never touch the Markdown or count as unsaved changes.
  await expect(reviewer.locator("#markdown-source")).toHaveValue(markdown);
  await expect(reviewer.locator("#save-status")).toHaveText("Saved");

  // AC1: teammate B sees A's comment but cannot change it.
  const teammateContext = await browser.newContext();
  const teammate = await teammateContext.newPage();
  const teammateEmail = await register(teammate, "Teammate B");
  joinTeam(reviewerEmail, teammateEmail);
  await teammate.goto(projectUrl);
  await expect(teammate.locator(".react-flow__node")).toHaveCount(2);
  await expect(teammate.locator('.react-flow__node[data-id="Node_Greeting"] .dlg-node__comments')).toHaveText("1 comment");
  const seen = await openNode(teammate, "Node_Greeting");
  const seenComment = seen.locator(".node-comment");
  await expect(seenComment.locator(".node-comment-body")).toHaveText("Is the greeting too <b>formal</b>?");
  await expect(seenComment.getByRole("button", { name: "Edit" })).toHaveCount(0);
  await expect(seenComment.getByRole("button", { name: "Delete" })).toHaveCount(0);
  await seen.getByLabel("Add a comment").fill("SECRET-REVIEW-NOTE from B");
  await seen.getByRole("button", { name: "Add comment", exact: true }).click();
  await expect(seen.locator(".node-comment")).toHaveCount(2);
  await teammateContext.close();

  // A refreshes and sees B's comment, without controls for it.
  await comments.getByRole("button", { name: "Refresh comments", exact: true }).click();
  await expect(comments.locator(".node-comment")).toHaveCount(2);
  const fromTeammate = comments.locator(".node-comment").filter({ hasText: "SECRET-REVIEW-NOTE" });
  await expect(fromTeammate.getByRole("button", { name: "Edit" })).toHaveCount(0);
  await expect(reviewer.locator('.react-flow__node[data-id="Node_Greeting"] .dlg-node__comments')).toHaveText("2 comments");

  // AC3: the export leaves comments out.
  const download = reviewer.waitForEvent("download");
  await reviewer.getByRole("button", { name: "Export JSON", exact: true }).click();
  const exported = await readFile((await (await download).path())!, "utf8");
  expect(exported).toContain("Welcome, traveler.");
  expect(exported).not.toContain("SECRET-REVIEW-NOTE");
  expect(exported).not.toContain("formal");

  // AC2: A edits, then deletes, their own comment; the dialogue stays the same.
  const mine = comments.locator(".node-comment").filter({ hasText: "Reviewer A" });
  await mine.getByRole("button", { name: "Edit", exact: true }).click();
  await mine.getByLabel("Edit comment").fill("The greeting works.");
  await mine.getByRole("button", { name: "Save", exact: true }).click();
  await expect(mine.locator(".node-comment-body")).toHaveText("The greeting works.");
  await expect(mine.locator(".node-comment-edited")).toHaveText("(edited)");

  reviewer.once("dialog", dialog => dialog.accept());
  await mine.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(comments.locator(".node-comment")).toHaveCount(1);
  await expect(reviewer.locator('.react-flow__node[data-id="Node_Greeting"] .dlg-node__comments')).toHaveText("1 comment");
  await expect(reviewer.locator("#markdown-source")).toHaveValue(markdown);
  await expect(reviewer.locator("#save-status")).toHaveText(/^Exported /);

  // Undo restores the deleted node, but not the comment deleted before it.
  const badge = reviewer.locator('.react-flow__node[data-id="Node_Greeting"] .dlg-node__comments');
  reviewer.once("dialog", dialog => dialog.accept());
  await reviewer.getByRole("button", { name: /^Delete selected/ }).click();
  await expect(reviewer.locator(".react-flow__node")).toHaveCount(1);
  await reviewer.locator("#parse-status").click();
  await reviewer.keyboard.press("ControlOrMeta+z");
  await expect(reviewer.locator(".react-flow__node")).toHaveCount(2);
  await expect(badge).toHaveText("1 comment");
  const restored = await openNode(reviewer, "Node_Greeting");
  await expect(restored.locator(".node-comment")).toHaveCount(1);
  await expect(restored.locator(".node-comment-body")).toHaveText("SECRET-REVIEW-NOTE from B");
});

test("unsent comments stay with their node and leaving asks first", async ({ page }) => {
  await register(page, "Reviewer D");
  await page.getByLabel("Project name").fill(`Drafts ${randomUUID()}`);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.locator("#markdown-source")).toBeEnabled();
  await page.locator("#markdown-source").fill(markdown);
  await page.getByRole("button", { name: "Parse Markdown" }).click();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.locator("#save-status")).toHaveText("Saved");
  await expect(page.locator("#parse-status")).toHaveText("Graph matches this Markdown");

  const close = page.getByRole("button", { name: "Close node details", exact: true });
  const comments = await openNode(page, "Node_Greeting");
  const input = comments.getByLabel("Add a comment");
  await input.fill("Half a thought");
  await close.click();
  await openNode(page, "Node_Shop");
  await expect(input).toHaveValue("");
  await close.click();
  await openNode(page, "Node_Greeting");
  await expect(input).toHaveValue("Half a thought");
  await expect(page.locator("#save-status")).toHaveText("Saved");

  const messages: string[] = [];
  let accept = false;
  page.on("dialog", dialog => {
    messages.push(`${dialog.type()}: ${dialog.message()}`);
    return accept ? dialog.accept() : dialog.dismiss();
  });
  const back = page.getByRole("link", { name: "← Projects", exact: true });
  await back.click();
  await expect(page.locator("#editor")).toBeVisible();
  await expect(input).toHaveValue("Half a thought");
  accept = true;
  await back.click();
  await expect(page.getByRole("heading", { name: "Your projects", exact: true })).toBeVisible();
  expect(messages).toEqual(Array(2).fill("confirm: You have a comment that is not sent. Leave without it?"));
});

test("a node that is not saved yet cannot get a comment", async ({ page }) => {
  await register(page, "Reviewer C");
  await page.getByLabel("Project name").fill(`Unsaved ${randomUUID()}`);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.locator("#markdown-source")).toBeEnabled();
  await page.locator("#markdown-source").fill(markdown);
  await page.getByRole("button", { name: "Parse Markdown" }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(2);

  const comments = await openNode(page, "Node_Shop");
  await comments.getByLabel("Add a comment").fill("Too early");
  await comments.getByRole("button", { name: "Add comment", exact: true }).click();
  await expect(comments.locator("#node-comment-error")).toHaveText("Save the project before commenting on new nodes.");
  await expect(comments.getByLabel("Add a comment")).toHaveValue("Too early");
  await expect(comments.locator(".node-comment")).toHaveCount(0);
});
