// Recovery after a save is rejected because someone saved a newer version (409).
// The editor keeps its text; the user copies it or loads the latest version.

import type { ProjectSnapshot } from "./api";

export interface Clipboard { writeText(text: string): Promise<void> }

export async function copyText(text: string, clipboard: Clipboard | undefined): Promise<boolean> {
  if (!clipboard) return false;
  try {
    await clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

// The editor state changes only after the latest version arrives.
// A failed read leaves everything as it was.
export async function loadLatest(steps: {
  setBusy(busy: boolean): void;
  open(): Promise<ProjectSnapshot>;
  apply(snapshot: ProjectSnapshot): void;
  fail(error: unknown): void;
}): Promise<ProjectSnapshot | null> {
  steps.setBusy(true);
  let snapshot: ProjectSnapshot;
  try {
    snapshot = await steps.open();
  } catch (error) {
    steps.setBusy(false);
    steps.fail(error);
    return null;
  }
  steps.apply(snapshot);
  steps.setBusy(false);
  return snapshot;
}

export function mountConflictRecovery(options: {
  panel: HTMLElement;
  dialog: HTMLDialogElement;
  markdown(): string;
  clipboard(): Clipboard | undefined;
  load(): Promise<boolean>;
}) {
  const { panel, dialog } = options;
  const find = <T extends HTMLElement>(root: ParentNode, id: string) => root.querySelector<T>(`#${id}`)!;
  const copyButton = find<HTMLButtonElement>(panel, "copy-markdown");
  const loadButton = find<HTMLButtonElement>(panel, "load-latest");
  const message = find(panel, "conflict-message");
  const feedback = find(panel, "conflict-feedback");
  const fallback = find(panel, "copy-fallback");
  const fallbackText = find<HTMLTextAreaElement>(panel, "copy-fallback-text");
  const confirm = find<HTMLButtonElement>(dialog, "load-latest-confirm");
  const cancel = find<HTMLButtonElement>(dialog, "load-latest-cancel");

  function hideFallback() { fallback.hidden = true; fallbackText.value = ""; }

  copyButton.addEventListener("click", async () => {
    const text = options.markdown();
    hideFallback();
    if (await copyText(text, options.clipboard())) {
      feedback.textContent = "Copied your Markdown.";
      return;
    }
    feedback.textContent = "";
    fallbackText.value = text;
    fallback.hidden = false;
    fallbackText.focus();
    fallbackText.select();
  });
  loadButton.addEventListener("click", () => dialog.showModal());
  cancel.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => { if (!panel.hidden) loadButton.focus(); });
  confirm.addEventListener("click", async () => {
    dialog.close();
    feedback.textContent = "";
    if (await options.load()) hide();
  });

  function show(notice: string) {
    panel.hidden = false;
    message.textContent = notice;
  }
  function hide() { panel.hidden = true; feedback.textContent = ""; hideFallback(); }
  function setDisabled(disabled: boolean) { copyButton.disabled = loadButton.disabled = disabled; }

  return { show, hide, setDisabled, get visible() { return !panel.hidden; } };
}
