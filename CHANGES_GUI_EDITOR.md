# GUI node editing prototype

This adds a node property editor to the existing React Flow + Django application.

## On macOS

In one terminal:

```sh
cd frontend
npm install
npm run dev
```

`npm run dev` builds assets in watch mode; it does **not** start the web server. Wait for `built in ...`.

In another terminal:

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## On Windows -- Please add 


Open http://127.0.0.1:8000/.

## Usage

1. Parse Markdown.
2. Click a graph node; an editor panel opens.
3. Edit speaker, audience, dialogue, and custom fields. Click Add field to add a new `@field_name: value` directive.
4. Click Apply to Markdown. This changes the Markdown source **without saving it or validating it**.
5. Click Parse again to validate and regenerate the graph, then Save to persist the draft.

## Limitations

- The original proof-of-concept syntax is retained: `# Node_ID`, `Speaker: text`, `* "Choice" -> Target`, `<<jump: Target>>`.
- Node IDs are read-only; renaming requires an atomic update of all inbound links.
- Editing is source-span-based and preserves unrelated lines (including jumps and choices) within a node, but moves edited dialogue to the start of the node. It does not yet preserve arbitrary interleaving of dialogue with jumps/mutations. Review changes before saving.
- Custom metadata is stored as raw text and not semantically validated. Fields such as `required_item` have no game-state behavior yet.
- This is a first GUI-editing pass, not the full AST round-trip compiler or the final Lark grammar.
