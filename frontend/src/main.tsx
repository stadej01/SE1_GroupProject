import "vite/modulepreload-polyfill";
import { createRoot } from "react-dom/client";
import type { Diagnostic, DialogueGraph as Graph, GraphNode, GraphEdge } from "./graph/contract";
import { DialogueGraph } from "./components/DialogueGraph";
import { EditingNodeContext } from "./components/DialogueNode";
import { sourceRange } from "./editor/source";
import { patchNodeSource } from "./editor/patchNode";
import { appendNode, appendConnection, removeConnection, locateNode, setStartNodes } from "./editor/graphEdits";
import { createStore, initializeEditor } from "./project/store";
import { applyLayout } from "./project/layout";
import { readCsrfToken } from "./project/csrf";
import { isDirty, canApplySubmittedSource } from "./project/dirty";
import { ProjectRequestError } from "./project/api";
import { projectErrorNotice } from "./project/errors";
import { showErrorNotice } from "./project/status";
import { createRequest } from "./project/request";
import { mountPanelDivider } from "./project/panelDivider";
import { mountToolbarMenus } from "./project/toolbarMenus";
import { mountLeaveDialog } from "./project/leaveDialog";
import { deleteSelection, inspectDeletion } from "./editor/deleteSelection";
import "./editor.css";

function element<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (!found) throw new Error(`Missing editor element: ${id}`);
  return found as T;
}

const app = element("editor");
const source = element<HTMLTextAreaElement>("markdown-source");
const parseButton = element<HTMLButtonElement>("parse-button");
const saveButton = element<HTMLButtonElement>("save-button");
const parseStatus = element("parse-status");
const saveStatus = element("save-status");
const graphCount = element("graph-count");
const lineNumbers = element("line-numbers");
const selection = element("source-selection");
const lineMark = document.createElement("div");
lineMark.id = "source-line-mark";
lineMark.className = "source-line-mark";
lineMark.hidden = true;
source.parentElement!.append(lineMark);
let markedLines: { first: number; last: number } | null = null;
const diagnosticPanel = element("diagnostics-panel");
const diagnosticList = element("diagnostics");
const getCsrfToken = () => readCsrfToken(document.cookie, app.dataset.csrfCookie!);
const request = createRequest(getCsrfToken);
const store = createStore({ openUrl: app.dataset.openUrl, saveUrl: app.dataset.saveUrl!, getCsrfToken, request });
const logoutForm = document.querySelector<HTMLFormElement>("#logout-form");
logoutForm?.addEventListener("submit", () => {
  logoutForm.querySelector<HTMLInputElement>('input[name="csrfmiddlewaretoken"]')!.value = getCsrfToken();
});
const root = createRoot(element("graph-root"));
const positions = new Map<string, { x: number; y: number }>();
let revision = Number(app.dataset.revision);
let savedSource = source.value;
let graphSource: string | null = null;
let generation = 0;
let parseRequest: AbortController | undefined;
let selectedNode: GraphNode | null = null;
let selectedNodeIds = new Set<string>();
let selectedEdgeIds = new Set<string>();
let editingGraph: Graph | null = null;
let pendingMarkdown: string | null = null;
let selectedNodeId: string | null = null;
let verticalLayout = false;
let rotateLabels = false;
let graphRenderVersion = 0;
let positionVersion = 0;
let savedPositionVersion = 0;
let activeSave: Promise<boolean> | null = null;
let leavingAfterSave = false;
function hasUnsavedChanges() {
  return isDirty({ source: source.value, savedSource, pendingMarkdown, project: store.project,
    positionVersion, savedPositionVersion });
}
function updateSaveStatus(cleanLabel = "No unsaved changes") {
  if (saveStatus.dataset.error !== "true") {
    saveStatus.textContent = hasUnsavedChanges() ? "Unsaved changes" : cleanLabel;
  }
}
function graphChanged(message: string) {
  parseStatus.textContent = message + " — press Parse to sync Markdown";
  graphCount.textContent = `${editingGraph?.nodes.length ?? 0} nodes · ${editingGraph?.edges.length ?? 0} connections · unsynced GUI edits`;
  graphRenderVersion++;
  updateSaveStatus();
  renderGraph();
}
function renderGraph() {
  refreshConnectionOptions();
  if (!editingGraph) return;
  root.render(<EditingNodeContext.Provider value={nodePanel.hidden ? null : selectedNodeId}><DialogueGraph key={graphRenderVersion + (verticalLayout ? 100000 : 0) + (rotateLabels ? 200000 : 0)} graph={editingGraph} savedPositions={positions}
  vertical={verticalLayout} rotateLabels={rotateLabels}
  onSelectEdge={selectEdge}
  onSelectionChange={(nodes, edges) => {
    selectedNodeIds = new Set(nodes);
    selectedEdgeIds = new Set(edges);
    refreshDeleteButton();
  }}
  onPaneClick={dismissNodeEditor}
    onSelectNode={selectNode} onMoveNode={(id, position) => {
      positions.set(id, { ...position });
      positionVersion++;
      updateSaveStatus();
    }}
    onConnectNodes={(from, to, kind, label) => {
      if (!editingGraph || from === to && !window.confirm("Connect this node to itself?")) return;
      try {
        createConnection(from, to, kind, label);
      } catch (e) { window.alert(e instanceof Error ? e.message : "Cannot connect nodes"); }
    }} /></EditingNodeContext.Provider>);
}

function selectEdge(edge: GraphEdge) {
  const selector = toolbar.querySelector<HTMLSelectElement>("#connection-delete");
  if (selector) selector.value = edge.id;
  parseStatus.textContent = `Selected connection: ${edge.source} → ${edge.target}. Open Connections to delete it.`;
  if (!pendingMarkdown && graphSource === source.value && edge.source_line > 0) markLines(edge.source_line);
  else clearLineMark();
}
function deleteConnection() {
  if (!editingGraph || graphSource !== source.value) { window.alert("Parse valid Markdown before editing connections."); return; }
  const selector = toolbar.querySelector<HTMLSelectElement>("#connection-delete")!;
  const edge = editingGraph.edges.find(item => item.id === selector.value);
  if (!edge) { window.alert("Select a connection to delete."); return; }
  try {
    const updated = removeConnection(pendingMarkdown ?? source.value, edge);
    pendingMarkdown = updated;
    editingGraph = { ...editingGraph, edges: editingGraph.edges.filter(item => item.id !== edge.id) };
    graphChanged("Connection deleted");
  } catch (error) { window.alert(error instanceof Error ? error.message : "Unable to delete connection"); }
}
function emptyGraph(message: string) {
  root.render(<div className="empty-state"><span className="empty-glyph" aria-hidden="true">↳</span><h3>Your story, connected.</h3><p>{message}</p></div>);
  graphSource = null;
  selectedNode = null;
  editingGraph = null;
  graphCount.textContent = "Not parsed";
  refreshConnectionOptions();
}

function updateLines() {
  const count = source.value.split("\n").length;
  lineNumbers.textContent = Array.from({ length: count }, (_, i) => i + 1).join("\n");
  element("line-count").textContent = `${count} lines`;
  lineNumbers.scrollTop = source.scrollTop;
  clearLineMark();
}

function selectLines(first: number, last = first, label?: string) {
  const range = sourceRange(source.value, first, last);
  source.setSelectionRange(range.start, range.end);
  const lineHeight = parseFloat(getComputedStyle(source).lineHeight);
  source.scrollTop = Math.max(0, (first - 3) * lineHeight);
  lineNumbers.scrollTop = source.scrollTop;
  selection.textContent = `Lines ${first}–${last}${label ? ` · ${label}` : ""}`;
}

// An error's line takes the user into the Markdown box to fix it.
function jumpToLine(line: number) {
  source.focus();
  selectLines(line);
}

// A graph selection only marks its lines. Focus stays out of the Markdown box,
// or the next key press would replace them and become a saved edit.
function markLines(first: number, last = first, label?: string) {
  selectLines(first, last, label);
  (document.activeElement as HTMLElement | null)?.blur();
  markedLines = { first, last };
  positionLineMark();
}

function positionLineMark() {
  lineMark.hidden = markedLines === null;
  if (!markedLines) return;
  const style = getComputedStyle(source);
  const lineHeight = parseFloat(style.lineHeight);
  lineMark.style.top = `${parseFloat(style.paddingTop) + (markedLines.first - 1) * lineHeight - source.scrollTop}px`;
  lineMark.style.height = `${(markedLines.last - markedLines.first + 1) * lineHeight}px`;
}

function clearLineMark() {
  markedLines = null;
  lineMark.hidden = true;
}

function selectNode(node: GraphNode) {
  // A source span belongs only to the exact snapshot that produced this graph.
  if (graphSource !== source.value) return;
  if (warnAboutUnappliedEdits()) return;
  selectedNode = node;
  selectedNodeId = node.id;
  if (node.source_line > 0 && !pendingMarkdown) markLines(node.source_line, node.source_end_line, node.id);
  else clearLineMark();
  showNodeEditor(node);
}

function showDiagnostics(diagnostics: Diagnostic[]) {
  diagnosticList.replaceChildren();
  diagnosticPanel.hidden = diagnostics.length === 0;
  const hasErrors = diagnostics.some(item => item.severity === "error");
  diagnosticPanel.dataset.severity = hasErrors ? "error" : "warning";
  element("diagnostics-heading").textContent = hasErrors ? "Markdown needs attention" : "Starting node required";
  element("diagnostics-help").textContent = hasErrors
    ? `You can still save this ${store.contentLabel}. Fix these issues before generating the graph.`
    : "Select a starting node before validating or playtesting the dialogue.";
  for (const diagnostic of diagnostics) {
    const li = document.createElement("li");
    const text = `${diagnostic.line ? `Line ${diagnostic.line}: ` : ""}${diagnostic.message}`;
    if (diagnostic.line) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = text;
      button.addEventListener("click", () => jumpToLine(diagnostic.line!));
      li.append(button);
    } else li.textContent = text;
    diagnosticList.append(li);
  }
}

async function parse(warnAboutStart = true) {
  if (parseButton.disabled) return;
  const submittedSource = pendingMarkdown ?? source.value;
  const submittedGeneration = ++generation;
  parseRequest?.abort();
  parseRequest = new AbortController();
  parseButton.disabled = true;
  parseStatus.textContent = "Parsing…";
  showDiagnostics([]);
  try {
    const reply = await request(app.dataset.syncUrl!, "POST", { markdown_source: submittedSource }, parseRequest.signal);
    if (submittedGeneration !== generation) return;
    if (reply.status === 401 || reply.status === 403) {
      // /sync checks login and CSRF; it does not check project membership.
      const error = new ProjectRequestError(reply.status, reply.status === 403 ? "CSRF Failed" : reply.detail);
      showErrorNotice(parseStatus, projectErrorNotice(error), app.dataset.loginUrl);
      return;
    }
    if (!reply.ok || !reply.graph) {
      emptyGraph("Fix the Markdown errors, then parse again.");
      showDiagnostics(reply.diagnostics ?? [{ severity: "error", message: "Parsing failed. Please try again." }]);
      parseStatus.textContent = "Graph blocked by errors";
      return;
    }
    const graph = reply.graph;
    if (pendingMarkdown !== null) {
      source.value = submittedSource;
      pendingMarkdown = null;
      updateLines();
    }
    graphSource = submittedSource;
    editingGraph = graph;
    closeNodeEditor();
    renderGraph();
    graphCount.textContent = `${graph.nodes.length} nodes · ${graph.edges.length} connections`;
    parseStatus.textContent = "Graph matches this Markdown";
    showDiagnostics(graph.diagnostics);
    updateSaveStatus();
    if (warnAboutStart && graph.start_nodes.length === 0) {
      window.alert("Starting nodes have not been allocated. Select one or more starting nodes before validating or playtesting the dialogue.");
    }
  } catch (error) {
    if (submittedGeneration !== generation) return;
    emptyGraph("The graph could not be generated. Your Markdown is still available.");
    showDiagnostics([{ severity: "error", message: error instanceof Error ? error.message : "Request failed." }]);
    parseStatus.textContent = "Parse failed";
  } finally {
    if (submittedGeneration === generation) parseButton.disabled = false;
  }
}

// A second request joins the save that is already running.
function save(): Promise<boolean> {
  activeSave ??= submitSave().finally(() => { activeSave = null; });
  return activeSave;
}

async function submitSave(): Promise<boolean> {
  if (saveButton.disabled) return false;
  const submittedSource = pendingMarkdown ?? source.value;
  const submittedPositionVersion = positionVersion;
  saveButton.disabled = true;
  saveStatus.dataset.error = "false";
  saveStatus.textContent = "Saving…";
  try {
    const reply = await store.save(submittedSource, revision, editingGraph, positions, verticalLayout);
    revision = reply.revision;
    savedSource = submittedSource;
    savedPositionVersion = submittedPositionVersion;
    const applySubmittedSource = canApplySubmittedSource(pendingMarkdown, submittedSource);
    if (applySubmittedSource) {
      source.value = submittedSource;
      pendingMarkdown = null;
      updateLines();
      graphSource = submittedSource;
    }
    updateSaveStatus(store.savedLabel);
    if (applySubmittedSource && !leavingAfterSave) void parse();
    return true;
  } catch (error) {
    showErrorNotice(saveStatus, store.project ? projectErrorNotice(error)
      : { message: error instanceof Error ? error.message : store.failedLabel }, app.dataset.loginUrl);
    return false;
  } finally { saveButton.disabled = false; }
}

// A save that was already running may not include the newest edits.
async function saveBeforeLeaving(): Promise<boolean> {
  leavingAfterSave = true;
  const saved = (!activeSave || await activeSave) && (!hasUnsavedChanges() || await save());
  if (!saved) leavingAfterSave = false;
  return saved;
}

source.addEventListener("input", () => {
  generation++;
  parseRequest?.abort();
  parseButton.disabled = false;
  pendingMarkdown = null;
  emptyGraph("Markdown changed. Parse again to refresh the graph.");
  closeNodeEditor();
  showDiagnostics([]);
  parseStatus.textContent = "Edited — parse again";
  selection.textContent = "Select a node to find its source.";
  updateSaveStatus();
  updateLines();
});
source.addEventListener("scroll", () => { lineNumbers.scrollTop = source.scrollTop; positionLineMark(); });
source.addEventListener("focus", clearLineMark);
parseButton.addEventListener("click", () => { void parse(); });
saveButton.addEventListener("click", () => { void save(); });
const backLink = document.querySelector<HTMLAnchorElement>("#back-to-projects");
const leaveDialog = document.querySelector<HTMLDialogElement>("#leave-dialog");
const leaveGuard = backLink && leaveDialog
  ? mountLeaveDialog({ link: backLink, dialog: leaveDialog, hasUnsavedChanges, save: saveBeforeLeaving })
  : null;
document.addEventListener("keydown", (event) => {
  if (!(event.ctrlKey || event.metaKey)) return;
  if (event.key === "Enter") { event.preventDefault(); if (!leaveGuard?.open) void parse(); }
  if (event.key.toLowerCase() === "s") { event.preventDefault(); if (!leaveGuard?.open) void save(); }
});
window.addEventListener("beforeunload", (event) => {
  if (hasUnsavedChanges() && !leaveGuard?.confirmed) { event.preventDefault(); event.returnValue = ""; }
});
mountPanelDivider(element("workspace"), element("panel-divider"));
updateLines();

// GUI edits remain in a pending buffer until Parse (or Save Draft) is pressed.
const nodePanel = document.createElement("section");
nodePanel.className = "node-edit-panel";
nodePanel.hidden = true;
nodePanel.innerHTML = `<header class="node-edit-header"><h3>Edit selected node</h3><button type="button" id="dismiss-node-editor" aria-label="Close node details">×</button></header><p class="node-edit-help">Changes update the graph immediately. Press Parse to sync them to Markdown.</p><form id="node-edit-form"><label>Node ID<input name="node_id" readonly></label><label>Speaker (required)<input name="speaker" required></label><label>Audience (comma-separated)<input name="audience"></label><label>Dialogue (one line per paragraph)<textarea name="dialogue" rows="5" required></textarea></label><h4>Additional fields</h4><div id="node-extra-fields"></div><button type="button" id="add-node-field">+ Add field</button><div class="node-edit-actions"><button type="submit">Apply to Markdown</button><button type="button" id="close-node-editor">Cancel</button></div><p id="node-edit-error" role="alert"></p></form>`;
app.append(nodePanel);
const editForm = nodePanel.querySelector<HTMLFormElement>("#node-edit-form")!;
const extras = nodePanel.querySelector<HTMLElement>("#node-extra-fields")!;
const nodeEditError = nodePanel.querySelector<HTMLElement>("#node-edit-error")!;
let appliedFormValues = "";
function formValues() {
  return JSON.stringify([...editForm.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>("input, textarea")].map(field => field.value));
}
function fieldInput(name: string, value: string) {
  const row = document.createElement("div"); row.className = "node-extra-row";
  const key = document.createElement("input"); key.placeholder = "field_name"; key.value = name; key.setAttribute("aria-label", "Field name");
  const val = document.createElement("input"); val.placeholder = "Value"; val.value = value; val.setAttribute("aria-label", "Field value");
  const remove = document.createElement("button"); remove.type = "button"; remove.textContent = "×"; remove.setAttribute("aria-label", "Remove field"); remove.addEventListener("click", () => row.remove());
  row.append(key, val, remove); extras.append(row);
}
function closeNodeEditor() { nodePanel.hidden = true; clearLineMark(); renderGraph(); }
// Clicks on the graph must not lose text the user has not applied yet.
function warnAboutUnappliedEdits() {
  if (nodePanel.hidden || formValues() === appliedFormValues) return false;
  nodeEditError.textContent = "These changes are not applied. Click Apply to Markdown to keep them, or Cancel to discard them.";
  nodeEditError.scrollIntoView({ block: "nearest" });
  return true;
}
function dismissNodeEditor() {
  if (!warnAboutUnappliedEdits()) closeNodeEditor();
}
function showNodeEditor(node: GraphNode) {
  nodePanel.hidden = false;
  const data = node.dialogue_lines ?? [];
  const metadata = node.metadata ?? {};
  (editForm.elements.namedItem("node_id") as HTMLInputElement).value = node.id;
  (editForm.elements.namedItem("speaker") as HTMLInputElement).value = metadata.speaker || data[0]?.speaker || "";
  (editForm.elements.namedItem("audience") as HTMLInputElement).value = metadata.audience || "";
  (editForm.elements.namedItem("dialogue") as HTMLTextAreaElement).value = data.map(d => d.text).join("\n");
  extras.replaceChildren();
  for (const [k, v] of Object.entries(metadata)) if (k !== "speaker" && k !== "audience") fieldInput(k, v);
  nodeEditError.textContent = "";
  appliedFormValues = formValues();
  renderGraph();
}
nodePanel.querySelector("#add-node-field")!.addEventListener("click", () => fieldInput("", ""));
nodePanel.querySelector("#close-node-editor")!.addEventListener("click", closeNodeEditor);
nodePanel.querySelector("#dismiss-node-editor")!.addEventListener("click", closeNodeEditor);
editForm.addEventListener("submit", event => {
  event.preventDefault();
  if (!selectedNode || !editingGraph || graphSource !== source.value) return;
  const fields: Record<string, string> = {};
  for (const name of ["node_id", "speaker", "audience"]) fields[name] = (editForm.elements.namedItem(name) as HTMLInputElement).value;
  for (const row of extras.querySelectorAll(".node-extra-row")) {
    const inputs = row.querySelectorAll("input");
    const key = inputs[0].value.trim();
    if (!key && !inputs[1].value.trim()) continue;
    if (!key || key in fields) { nodeEditError.textContent = "Field names must be nonempty and unique."; return; }
    fields[key] = inputs[1].value;
  }
  try {
    const current = pendingMarkdown ?? source.value;
    const located = locateNode(current, selectedNode.id);
    pendingMarkdown = patchNodeSource(current, { ...selectedNode, ...located }, fields, (editForm.elements.namedItem("dialogue") as HTMLTextAreaElement).value);
    const dialogue = (editForm.elements.namedItem("dialogue") as HTMLTextAreaElement).value.split("\n");
    const metadata = Object.fromEntries(Object.entries(fields).filter(([k]) => k !== "node_id" && k !== "speaker"));
    editingGraph = { ...editingGraph, nodes: editingGraph.nodes.map(n => n.id !== selectedNode!.id ? n : {
      ...n, metadata, category: metadata.category ?? n.category, color: metadata.color ?? n.color,
      preview: `${fields.speaker}: ${dialogue[0]}`,
      dialogue_lines: dialogue.map((text, i) => ({ speaker: fields.speaker, text, source_line: n.source_line + i }))
    }) };
    selectedNode = editingGraph.nodes.find(n => n.id === selectedNodeId)!;
    graphChanged("Node edited");
    nodeEditError.textContent = "";
    appliedFormValues = formValues();
  } catch (error) { nodeEditError.textContent = error instanceof Error ? error.message : "Unable to edit node"; }
});

// Graph editing toolbar. All operations use the same pending Markdown buffer.
const toolbar = document.createElement("div");
toolbar.className = "graph-edit-toolbar";
toolbar.innerHTML = `<button type="button" id="new-graph-node">+ New node</button><details class="toolbar-menu starting-node-picker"><summary id="starting-node-summary">Starting nodes (none)</summary><fieldset id="starting-node-list" class="toolbar-panel"><legend>Select conversation entry nodes</legend></fieldset></details><details class="toolbar-menu"><summary id="connections-summary">Connections (0)</summary><div class="toolbar-panel connections-panel"><label>From <input id="connection-from" list="graph-node-options" aria-label="Connection source node" placeholder="Search nodes" autocomplete="off"></label><label>To <input id="connection-to" list="graph-node-options" aria-label="Connection target node" placeholder="Search nodes" autocomplete="off"></label><datalist id="graph-node-options"></datalist><label class="panel-row">Type <select id="connection-kind"><option value="choice">Player choice</option><option value="jump">Automatic jump</option></select></label><button type="button" id="add-graph-connection" class="panel-row">+ Connect nodes</button><span class="toolbar-note panel-row">Drag from a node's output handle to another node's input to connect.</span><hr class="panel-row"><label class="panel-row">Connections <select id="connection-delete" aria-label="Select connection to delete"></select></label><button type="button" id="delete-graph-connection" class="panel-row">Delete connection</button></div></details><details class="toolbar-menu"><summary id="view-summary">View</summary><div class="toolbar-panel view-panel"><label>Layout <select id="graph-layout"><option value="horizontal">Horizontal</option><option value="vertical">Vertical</option></select></label><label class="checkbox-row"><input type="checkbox" id="rotate-edge-labels"> Rotate connector text 90°</label></div></details>`;
toolbar.insertAdjacentHTML(
  "afterbegin",
  `<button type="button" id="delete-graph-selection" disabled>
    Delete selected
  </button>`
);

function refreshDeleteButton() {
  const button = toolbar.querySelector<HTMLButtonElement>(
    "#delete-graph-selection"
  );

  if (!button) return;

  const count = selectedNodeIds.size + selectedEdgeIds.size;

  button.disabled = count === 0;
  button.textContent = count
    ? `Delete selected (${count})`
    : "Delete selected";
}
function refreshConnectionOptions() {
  const from = toolbar.querySelector<HTMLInputElement>("#connection-from")!;
  const to = toolbar.querySelector<HTMLInputElement>("#connection-to")!;
  const datalist = toolbar.querySelector<HTMLDataListElement>("#graph-node-options")!;
  const ids = (editingGraph?.nodes ?? []).map(node => node.id);
  datalist.replaceChildren(...ids.map(id => {
    const option = document.createElement("option"); option.value = id; return option;
  }));
  const startList = toolbar.querySelector<HTMLFieldSetElement>("#starting-node-list")!;
  const startNodes = new Set(editingGraph?.start_nodes ?? []);
  startList.replaceChildren(...ids.map(id => {
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = id;
    checkbox.checked = startNodes.has(id);
    label.append(checkbox, document.createTextNode(id));
    return label;
  }));
  toolbar.querySelector<HTMLElement>("#starting-node-summary")!.textContent =
    `Starting nodes (${startNodes.size || "none"})`;
  if (!ids.includes(from.value)) from.value = ids[0] ?? "";
  if (!ids.includes(to.value)) to.value = ids.find(id => id !== from.value) ?? ids[0] ?? "";
  const del = toolbar.querySelector<HTMLSelectElement>("#connection-delete")!;
  const old = del.value;
  del.replaceChildren(...(editingGraph?.edges ?? []).map(edge => {
    const option = document.createElement("option");
    option.value = edge.id;
    option.textContent = `${edge.source} → ${edge.target} (${edge.kind}${edge.label ? `: ${edge.label}` : ""})`;
    return option;
  }));
  if ((editingGraph?.edges ?? []).some(edge => edge.id === old)) del.value = old;
  toolbar.querySelector<HTMLElement>("#connections-summary")!.textContent =
    `Connections (${editingGraph?.edges.length ?? 0})`;
}
function createConnection(from: string, to: string, kind: "choice" | "jump", label: string) {
  if (!editingGraph) throw new Error("Parse Markdown before connecting nodes.");
  if (!editingGraph.nodes.some(n => n.id === from) || !editingGraph.nodes.some(n => n.id === to)) {
    throw new Error("Both source and target must exist.");
  }
  pendingMarkdown = appendConnection(pendingMarkdown ?? source.value, from, to, kind, label);
  editingGraph = { ...editingGraph, edges: [...editingGraph.edges, {
    id: `gui_${Date.now()}_${editingGraph.edges.length}`, source: from, target: to,
    kind, label: kind === "choice" ? label : null, condition: null, source_line: 0
  }] };
  graphChanged("Connection added");
}
element("graph-panel-header").append(toolbar);
mountToolbarMenus(toolbar);
toolbar.querySelector<HTMLButtonElement>("#add-graph-connection")!.addEventListener("click", () => {
  const from = toolbar.querySelector<HTMLInputElement>("#connection-from")!.value;
  const to = toolbar.querySelector<HTMLInputElement>("#connection-to")!.value;
  const kind = toolbar.querySelector<HTMLSelectElement>("#connection-kind")!.value as "choice" | "jump";
  if (!from || !to) { window.alert("Create at least one node before connecting."); return; }
  const label = kind === "choice" ? window.prompt("Choice text:", "Continue") : "";
  if (label === null || (kind === "choice" && !label.trim())) return;
  try { createConnection(from, to, kind, label); }
  catch (error) { window.alert(error instanceof Error ? error.message : "Cannot connect nodes"); }
});
toolbar.querySelector<HTMLButtonElement>("#delete-graph-connection")!.addEventListener("click", deleteConnection);
toolbar.querySelector<HTMLFieldSetElement>("#starting-node-list")!.addEventListener("change", event => {
  if (!editingGraph || graphSource !== source.value) return;
  const starts = [...toolbar.querySelectorAll<HTMLInputElement>("#starting-node-list input:checked")].map(input => input.value);
  try {
    pendingMarkdown = setStartNodes(pendingMarkdown ?? source.value, starts);
    editingGraph = { ...editingGraph, start_nodes: starts };
    graphChanged(starts.length ? `${starts.length} starting node${starts.length === 1 ? "" : "s"} selected` : "Starting nodes cleared");
  } catch (error) {
    window.alert(error instanceof Error ? error.message : "Unable to update starting node.");
    refreshConnectionOptions();
  }
});
toolbar.querySelector<HTMLButtonElement>("#new-graph-node")!.addEventListener("click", () => {
  if (!editingGraph || graphSource !== source.value) { window.alert("Parse valid Markdown before adding a node."); return; }
  const id = window.prompt("New node ID (letters, numbers, underscores):", "New_Dialogue_Node");
  if (id === null) return;
  const nodeId = id.trim();
  if (!/^\w+$/.test(nodeId) || editingGraph.nodes.some(n => n.id === nodeId)) { window.alert("Enter a unique node ID using letters, numbers, or underscores."); return; }
  const speaker = window.prompt("Speaker:", "Narrator");
  if (speaker === null || !/^\w[\w ]*$/.test(speaker.trim())) { window.alert("A valid speaker is required."); return; }
  const dialogue = window.prompt("Dialogue:", "New dialogue line");
  if (dialogue === null || !dialogue.trim() || dialogue.includes("\n")) { window.alert("Enter a nonempty, single-line dialogue."); return; }
  pendingMarkdown = appendNode(pendingMarkdown ?? source.value, nodeId, speaker.trim(), dialogue.trim());
  editingGraph = { ...editingGraph, nodes: [...editingGraph.nodes, { id: nodeId, category: null, color: null, preview: `${speaker}: ${dialogue}`, metadata: { speaker: speaker.trim() }, dialogue_lines: [{ speaker: speaker.trim(), text: dialogue.trim(), source_line: 0 }], source_line: 0, source_end_line: 0 }] };
  graphChanged("Node added");
});
toolbar.querySelector<HTMLSelectElement>("#graph-layout")!.addEventListener("change", event => {
  verticalLayout = (event.target as HTMLSelectElement).value === "vertical";
  positions.clear();
  positionVersion++;
  updateSaveStatus();
  renderGraph();
});
toolbar.querySelector<HTMLInputElement>("#rotate-edge-labels")!.addEventListener("change", event => {
  rotateLabels = (event.target as HTMLInputElement).checked;
  renderGraph();
});

emptyGraph("Parse the Markdown to see dialogue nodes, choices, and jumps.");
void initializeEditor(store, {
  setEnabled: enabled => { source.disabled = parseButton.disabled = saveButton.disabled = !enabled; toolbar.inert = !enabled; },
  restore: snapshot => {
    source.value = snapshot.markdown_source; savedSource = source.value; updateLines();
    revision = snapshot.revision; applyLayout(positions, snapshot.layout_data);
  },
  setStatus: (message, error, signIn) => {
    if (error) showErrorNotice(saveStatus, { message, signIn }, app.dataset.loginUrl);
    else { saveStatus.textContent = message; saveStatus.dataset.error = "false"; }
  },
  parse: () => parse(false),
});
