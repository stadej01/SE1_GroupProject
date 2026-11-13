// "Export unsaved changes?" dialog: save first, export the editor text as it is, or cancel.

export type ExportChoice = "save" | "unsaved" | "cancel";

export interface ExportDialog extends EventTarget {
  querySelector<E extends Element = Element>(selector: string): E | null;
  showModal(): void;
  close(): void;
}

export function askExportChoice(dialog: ExportDialog): Promise<ExportChoice> {
  return new Promise(resolve => {
    const listeners = new AbortController();
    const finish = (choice: ExportChoice) => {
      listeners.abort();
      dialog.close();
      resolve(choice);
    };
    const on = (id: string, choice: ExportChoice) =>
      dialog.querySelector<HTMLButtonElement>(`#${id}`)!
        .addEventListener("click", () => finish(choice), { signal: listeners.signal });
    on("export-save", "save");
    on("export-unsaved", "unsaved");
    on("export-cancel", "cancel");
    
    // Escape closes the dialog.
    dialog.addEventListener("cancel", () => finish("cancel"), { signal: listeners.signal });
    dialog.showModal();
  });
}
