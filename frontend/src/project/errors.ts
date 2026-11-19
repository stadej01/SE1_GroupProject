import { ProjectRequestError } from "./api";

export interface ErrorNotice { message: string; signIn?: boolean }

export function projectErrorNotice(error: unknown, operation: "save" | "open" = "save"): ErrorNotice {
  const opening = operation === "open";
  const retained = opening ? "The project could not be opened." : "Your text is still here.";
  if (!(error instanceof ProjectRequestError)) {
    return { message: `The server had a problem. ${retained}` };
  }
  const { status, detail, revision, isJson } = error;
  if (status === null) return { message: opening
    ? "Could not reach the server. Refresh later to try opening this project again."
    : "Could not reach the server. Your text is still here. Try again." };
  if (!isJson) return { message: `The server had a problem (${status}). ${retained}` };
  switch (status) {
    case 409:
      return { message: `A newer version was saved${revision === undefined ? "" : ` (revision ${revision})`}. Your text is still here. Copy it, then reload.` };
    case 401:
      return { message: `You are signed out. ${retained}`, signIn: true };
    case 403:
      if (typeof detail === "string" && detail.startsWith("CSRF Failed")) {
        return { message: opening ? "Security check failed. Reload to try opening this project again."
          : "Security check failed. Copy your text, then reload." };
      }
      return { message: opening ? "You do not have access to open this project."
        : "You no longer have access to this project. Your text is still here." };
    case 404:
      return { message: opening ? "This project no longer exists and cannot be opened."
        : "This project no longer exists. Copy your text." };
    case 503:
      return { message: opening ? "Project storage is not available right now. Refresh later to try opening this project again."
        : "Project storage is not available right now. Nothing was saved. Try again later." };
    case 400:
      return { message: opening ? "The server could not open this project."
        : "The server could not accept this save. Your text is still here." };
    default:
      return { message: `The server had a problem (${status}). ${retained}` };
  }
}
