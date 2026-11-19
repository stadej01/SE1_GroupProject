import type { ErrorNotice } from "./errors";

export function showErrorNotice(element: HTMLElement, notice: ErrorNotice, loginUrl?: string): void {
  element.dataset.error = "true";
  element.textContent = notice.message;
  if (notice.signIn && loginUrl) {
    const link = document.createElement("a");
    link.href = loginUrl;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "Sign in in a new tab";
    element.append(" ", link);
  }
}
