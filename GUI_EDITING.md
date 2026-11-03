# GUI Editing V2 (experimental)

## New controls
- Parse a valid draft first.
- Click a node to edit its fields; Apply changes updates the *visual graph* and stages Markdown modifications in memory.
- + New node creates a node with a unique ID, speaker, and initial dialogue.
- Drag from a node output handle to another node input handle to create a choice or jump; the choice dialog requests a label.
- Layout changes between horizontal and vertical. Rotate connector text rotates labels by 90 degrees.
- Press Parse to validate all staged GUI changes and transfer them to the Markdown textarea. If validation fails, Markdown is not replaced and the staged GUI changes remain for correction.
- Save Draft is disabled while GUI changes are staged; press Parse first. Drafts with invalid manually edited Markdown remain savable.

## Known limitations
- This is a prototype, not a full AST-based round-trip serializer. Source text is patched in place to retain existing comments and commands where possible.
- The graph layout selection and dragged node positions are browser-session-only, not persisted to the database.
- Connections can be created, but edge editing/deleting is not yet implemented.
- Existing node IDs cannot be renamed through the editor.
- Vertical layout uses a basic column-to-row transpose, not a full collision-free vertical router. Loop routing in vertical mode falls back to ordinary edges.
- The JavaScript build could not be verified in this environment because npm dependency installation timed out; run npm install and npm run build locally before use.
