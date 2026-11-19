export interface EditState {
  source: string;
  savedSource: string;
  pendingMarkdown: string | null;
  project: boolean;
  positionVersion: number;
  savedPositionVersion: number;
}

export function isDirty(state: EditState): boolean {
  return state.source !== state.savedSource
    || state.pendingMarkdown !== null
    || (state.project && state.positionVersion !== state.savedPositionVersion);
}

export function canApplySubmittedSource(pendingMarkdown: string | null, submittedSource: string): boolean {
  return pendingMarkdown === submittedSource;
}
