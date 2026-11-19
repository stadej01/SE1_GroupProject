// Draggable line between the Markdown and graph panels.

export const DEFAULT_SOURCE_RATIO = 0.38;
export const MIN_SOURCE_WIDTH = 280;
export const MIN_GRAPH_WIDTH = 420;
const KEY_STEP = 24;
const LARGE_KEY_STEP = 96;
const STORAGE_KEY = "dialogue-editor.source-panel-ratio";
const STACKED_LAYOUT = "(max-width: 900px)";
const WIDTH_VARIABLE = "--source-panel-width";

export function clampSourceWidth(width: number, available: number): number {
  const largest = Math.max(MIN_SOURCE_WIDTH, available - MIN_GRAPH_WIDTH);
  return Math.round(Math.min(Math.max(width, MIN_SOURCE_WIDTH), largest));
}

export function sourceWidthFromRatio(ratio: number, available: number): number {
  return clampSourceWidth(ratio * available, available);
}

export function parseStoredRatio(stored: string | null): number {
  if (stored === null || !stored.trim()) return DEFAULT_SOURCE_RATIO;
  const ratio = Number(stored);
  return ratio > 0 && ratio < 1 ? ratio : DEFAULT_SOURCE_RATIO;
}

export function widthAfterKey(key: string, shift: boolean, width: number, available: number): number | null {
  const step = shift ? LARGE_KEY_STEP : KEY_STEP;
  switch (key) {
    case "ArrowLeft": return clampSourceWidth(width - step, available);
    case "ArrowRight": return clampSourceWidth(width + step, available);
    case "Home": return clampSourceWidth(0, available);
    case "End": return clampSourceWidth(Infinity, available);
    default: return null;
  }
}

// The separator reports its position as a percentage of the available width.
export function separatorValues(width: number, available: number) {
  const percent = (value: number) => Math.round(value / available * 100);
  return { now: percent(width), min: percent(clampSourceWidth(0, available)), max: percent(clampSourceWidth(Infinity, available)) };
}

// Private windows and blocked site data can make storage throw.
function readRatio(): number {
  try { return parseStoredRatio(window.localStorage.getItem(STORAGE_KEY)); }
  catch { return DEFAULT_SOURCE_RATIO; }
}
function writeRatio(ratio: number): void {
  try { window.localStorage.setItem(STORAGE_KEY, String(ratio)); }
  catch { /* The width still applies until the page closes. */ }
}
function clearRatio(): void {
  try { window.localStorage.removeItem(STORAGE_KEY); }
  catch { /* Nothing to clear. */ }
}

export function mountPanelDivider(workspace: HTMLElement, divider: HTMLElement): void {
  const stacked = window.matchMedia(STACKED_LAYOUT);
  let ratio = readRatio();
  let grabOffset: number | null = null;
  let moved = false;

  const available = () => workspace.clientWidth - divider.offsetWidth;
  const currentWidth = () => sourceWidthFromRatio(ratio, available());

  function apply() {
    if (stacked.matches) { workspace.style.removeProperty(WIDTH_VARIABLE); return; }
    const width = currentWidth();
    const values = separatorValues(width, available());
    workspace.style.setProperty(WIDTH_VARIABLE, `${width}px`);
    divider.setAttribute("aria-valuenow", String(values.now));
    divider.setAttribute("aria-valuemin", String(values.min));
    divider.setAttribute("aria-valuemax", String(values.max));
  }
  function setWidth(width: number) {
    ratio = clampSourceWidth(width, available()) / available();
    apply();
  }

  divider.addEventListener("pointerdown", event => {
    if (event.button !== 0 || stacked.matches) return;
    divider.setPointerCapture(event.pointerId);
    grabOffset = event.clientX - divider.getBoundingClientRect().left;
    moved = false;
    document.body.classList.add("is-resizing-panels");
  });
  divider.addEventListener("pointermove", event => {
    if (grabOffset === null) return;
    moved = true;
    setWidth(event.clientX - grabOffset - workspace.getBoundingClientRect().left);
  });
  const endDrag = () => {
    if (grabOffset === null) return;
    grabOffset = null;
    document.body.classList.remove("is-resizing-panels");
    if (moved) writeRatio(ratio);
  };
  divider.addEventListener("pointerup", endDrag);
  divider.addEventListener("pointercancel", endDrag);
  divider.addEventListener("lostpointercapture", endDrag);

  divider.addEventListener("dblclick", () => {
    ratio = DEFAULT_SOURCE_RATIO;
    clearRatio();
    apply();
  });
  divider.addEventListener("keydown", event => {
    const width = widthAfterKey(event.key, event.shiftKey, currentWidth(), available());
    if (width === null) return;
    event.preventDefault();
    setWidth(width);
    writeRatio(ratio);
  });

  window.addEventListener("resize", apply);
  stacked.addEventListener("change", apply);
  apply();
}
