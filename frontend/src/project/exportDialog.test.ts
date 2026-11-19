import { test } from "node:test";
import assert from "node:assert/strict";
import { askExportChoice, type ExportDialog } from "./exportDialog";

function fakeDialog() {
  const buttons = new Map(["export-save", "export-unsaved", "export-cancel"].map(id => [`#${id}`, new EventTarget()]));
  const dialog = Object.assign(new EventTarget(), {
    opened: 0,
    closed: 0,
    querySelector: (selector: string) => buttons.get(selector) ?? null,
    showModal() { this.opened += 1; },
    close() { this.closed += 1; },
  });
  const click = (id: string) => buttons.get(`#${id}`)!.dispatchEvent(new Event("click"));
  return { dialog: dialog as typeof dialog & ExportDialog, click };
}

for (const [id, choice] of [["export-save", "save"], ["export-unsaved", "unsaved"], ["export-cancel", "cancel"]] as const) {
  test(`${id} resolves "${choice}" and closes the dialog`, async () => {
    const { dialog, click } = fakeDialog();
    const answer = askExportChoice(dialog);
    assert.equal(dialog.opened, 1);
    click(id);
    assert.equal(await answer, choice);
    assert.equal(dialog.closed, 1);
  });
}

test("Escape cancels the export", async () => {
  const { dialog } = fakeDialog();
  const answer = askExportChoice(dialog);
  dialog.dispatchEvent(new Event("cancel"));
  assert.equal(await answer, "cancel");
});

test("a second click after choosing does nothing", async () => {
  const { dialog, click } = fakeDialog();
  const answer = askExportChoice(dialog);
  click("export-unsaved");
  click("export-save");
  assert.equal(await answer, "unsaved");
  assert.equal(dialog.closed, 1);
});

test("each export asks again", async () => {
  const { dialog, click } = fakeDialog();
  const first = askExportChoice(dialog);
  click("export-cancel");
  await first;
  const second = askExportChoice(dialog);
  click("export-save");
  assert.equal(await second, "save");
  assert.equal(dialog.opened, 2);
});
