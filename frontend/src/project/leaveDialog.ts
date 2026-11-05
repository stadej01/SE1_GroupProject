// "Save or discard" dialog for leaving a project from inside the app.
// Browsers do not allow custom text when a tab closes; that case keeps the native prompt.

export interface LeaveClick {
  button: number;
  metaKey: boolean;
  ctrlKey: boolean;
  shiftKey: boolean;
  altKey: boolean;
}

// These clicks open the link elsewhere, so the current page keeps its work.
function opensElsewhere(click: LeaveClick): boolean {
  return click.button !== 0 || click.metaKey || click.ctrlKey || click.shiftKey || click.altKey;
}

export function shouldConfirmLeave(click: LeaveClick, unsaved: boolean): boolean {
  return unsaved && !opensElsewhere(click);
}

export function mountLeaveDialog(options: {
  link: HTMLAnchorElement;
  dialog: HTMLDialogElement;
  hasUnsavedChanges(): boolean;
  save(): Promise<boolean>;
}) {
  const { link, dialog, hasUnsavedChanges, save } = options;
  const button = (id: string) => dialog.querySelector<HTMLButtonElement>(`#${id}`)!;
  const saveAndLeave = button("leave-save");
  const discard = button("leave-discard");
  const cancel = button("leave-cancel");
  let saving = false;
  let confirmed = false;

  function setSaving(value: boolean) {
    saving = value;
    saveAndLeave.disabled = discard.disabled = cancel.disabled = value;
  }
  function leave() {
    confirmed = true;
    window.location.assign(link.href);
  }

  link.addEventListener("click", event => {
    if (!shouldConfirmLeave(event, hasUnsavedChanges())) return;
    event.preventDefault();
    dialog.showModal();
  });
  saveAndLeave.addEventListener("click", async () => {
    setSaving(true);
    if (await save()) { leave(); return; }
    setSaving(false);
    dialog.close();
  });
  discard.addEventListener("click", leave);
  cancel.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => { if (!confirmed) link.focus(); });
  dialog.addEventListener("cancel", event => { if (saving) event.preventDefault(); });
  // A disabled button loses focus, so Escape may not reach the dialog itself.
  document.addEventListener("keydown", event => {
    if (saving && event.key === "Escape") event.preventDefault();
  }, true);
  // The Back button can restore this page after the user left it.
  window.addEventListener("pageshow", event => {
    if (!event.persisted) return;
    confirmed = false;
    setSaving(false);
    if (dialog.open) dialog.close();
  });

  return {
    get open() { return dialog.open; },
    get confirmed() { return confirmed; },
  };
}
