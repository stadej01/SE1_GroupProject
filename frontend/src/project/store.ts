import type { Diagnostic, DialogueGraph } from "../graph/contract";
import { openProject, saveProject, type ProjectSnapshot } from "./api";
import { fillMissingPositions, saveLayout, type Positions } from "./layout";
import { projectErrorNotice, type ErrorNotice } from "./errors";

type DraftRequest = (url: string, method: string, body: object) => Promise<{
  ok: boolean; revision?: number; diagnostics?: Diagnostic[];
}>;

export function createStore(options: { openUrl?: string; saveUrl: string; getCsrfToken: () => string; request: DraftRequest }) {
  const project = Boolean(options.openUrl);
  return {
    project,
    savedLabel: project ? "Saved" : "Draft saved",
    failedLabel: project ? "Project was not saved." : "Draft was not saved.",
    contentLabel: project ? "project" : "draft",
    async open(): Promise<ProjectSnapshot | null> {
      return project ? openProject(options.openUrl!) : null;
    },
    async save(markdown: string, revision: number, graph: DialogueGraph | null, positions: Positions, vertical: boolean) {
      if (project) {
        const layout = saveLayout(graph, positions, vertical);
        const reply = await saveProject(options.saveUrl, options.getCsrfToken(), {
          markdown_source: markdown, layout_data: layout, base_revision: revision,
        });
        if (typeof reply.revision !== "number") throw new Error("Project was not saved.");
        fillMissingPositions(positions, layout);
        return reply;
      }
      const reply = await options.request(options.saveUrl, "PUT", { markdown_source: markdown, revision });
      if (!reply.ok || typeof reply.revision !== "number") {
        throw new Error(reply.diagnostics?.map(item => item.message).join(" ") || "Draft was not saved.");
      }
      return { revision: reply.revision };
    },
  };
}

// Call after the editor controls exist. Failed opens must never unlock Save.
export async function initializeEditor(store: ReturnType<typeof createStore>, editor: {
  setEnabled(enabled: boolean): void;
  restore(snapshot: ProjectSnapshot): void;
  setStatus(message: string, error: boolean, signIn?: boolean): void;
  parse(): Promise<void>;
}): Promise<void> {
  if (!store.project) { editor.setEnabled(true); return; }
  editor.setEnabled(false);
  try {
    const snapshot = (await store.open())!;
    editor.restore(snapshot);
    editor.setStatus("Saved", false);
    editor.setEnabled(true);
    if (snapshot.markdown_source.trim()) await editor.parse();
  } catch (error) {
    editor.setEnabled(false);
    const notice: ErrorNotice = projectErrorNotice(error, "open");
    editor.setStatus(notice.message, true, notice.signIn);
  }
}
