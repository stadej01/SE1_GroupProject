
# Current demo settings (sprint merge)

There are currently two independent Django configurations:

- `backend/config/settings.py` runs the dialogue editor using local SQLite.
- `backend/config/settings_neon.py` runs the accounts and teams demo using Neon PostgreSQL.

The demos use separate URL configurations in `backend/config/urls.py` and `backend/config/urls_neon.py`. The `settings_auth_test.py` configuration runs accounts and teams tests using local SQLite instead of Neon.

See the README for startup commands.

---

# File guide

This is a quick reference for the files we're most likely to touch while working on the dialogue editor. It covers our code and configuration, not installed packages, generated caches, or every Django boilerplate file.

## Django backend

| File | What it does |
| --- | --- |
| `backend/manage.py` | Runs Django commands such as `runserver`, `migrate`, and `test`. |
| `backend/requirements.txt` | Lists Python dependencies for both demos, including Django, django-environ, and psycopg. |
| `backend/config/settings.py` | Configures the dialogue editor using SQLite, including installed apps, templates, security settings, and static files. |
| `backend/config/urls.py` | Sends incoming URLs to the dialogue editor. |
| `backend/config/settings_neon.py` | Separate settings for the accounts and teams demo using Neon PostgreSQL. |
| `backend/config/urls_neon.py` | Routes the accounts and teams demo to Django admin and the health endpoint. |
| `backend/config/settings_auth_test.py` | Uses local SQLite to test accounts and teams without accessing Neon. |
| `backend/accounts/models.py` | Defines the custom email-based user model for the accounts demo. |
| `backend/teams/models.py` | Defines teams and team memberships. |
| `backend/accounts/tests.py` / `backend/teams/tests.py` | Tests authentication, user admin, and team membership. |
| `backend/config/asgi.py` / `backend/config/wsgi.py` | Standard Django entry points for hosting; we don't usually edit them during local development. |
| `backend/editor/urls.py` | Defines the page (`/`), parse (`/sync`), and save (`/save`) routes. |
| `backend/editor/views.py` | Handles loading the editor, validating/parsing Markdown, and saving drafts. Invalid drafts can still be saved. |
| `backend/editor/models.py` | Defines `Draft`, which stores Markdown and a revision number for each browser session. |
| `backend/editor/migrations/0001_initial.py` | Creates the draft table when you run migrations. |
| `backend/editor/assets.py` | Finds JavaScript and CSS assets built by Vite so Django can load them. |
| `backend/editor/templates/editor/index.html` | HTML layout for the two-panel page and buttons; React mounts the graph into this page. |
| `backend/editor/tests.py` | Django tests for the page, parse/save endpoints, draft behavior, and request handling. |

## Parsing and graph data

| File | What it does |
| --- | --- |
| `backend/dialogue_graph/stub_parser.py` | Temporary Markdown parser. Recognizes headers, dialogue lines, choices, jumps, conditions, and metadata; records source line numbers. We plan to replace it with Lark later. |
| `backend/dialogue_graph/validator.py` | Checks parser errors, duplicate IDs, blank choice labels, and links to missing nodes. |
| `backend/dialogue_graph/graph.py` | Converts validated parser output into the nodes and edges sent to React Flow. |
| `backend/dialogue_graph/__init__.py` | Exposes the parser and graph functions used by Django views. |
| `backend/dialogue_graph/__main__.py` | Command-line entry point for using the parser outside Django. |
| `backend/tests/test_graph.py` | Unit tests for parsing, validation, source lines, and graph connections. |

## React frontend

| File | What it does |
| --- | --- |
| `frontend/src/main.tsx` | Main editor code. Makes Django API requests, manages pending graph edits, and wires up the toolbar, selection, parsing, and saving. |
| `frontend/src/editor.css` | Styles for the editor page, toolbar, panels, and dialogs. |
| `frontend/src/components/DialogueGraph.tsx` | Renders the React Flow canvas, including node selection, dragging, and connections. |
| `frontend/src/components/DialogueNode.tsx` | Draws one node, including its ID, dialogue lines, color, and selection highlight. |
| `frontend/src/components/LoopEdge.tsx` | Custom drawing for loop and backward connections. |
| `frontend/src/components/dialogue-graph.css` | Styles specific to graph nodes and connections. |
| `frontend/src/graph/contract.ts` | TypeScript definitions for the graph data returned by Django; these must match the Python graph output. |
| `frontend/src/graph/toFlow.ts` | Turns graph data into React Flow nodes and edges, and calculates layouts and routes. |
| `frontend/src/editor/graphEdits.ts` | Adds new nodes and connections, and removes connections in pending Markdown. |
| `frontend/src/editor/patchNode.ts` | Updates a node's dialogue and metadata in Markdown while keeping its connections and unrelated lines. |
| `frontend/src/editor/source.ts` | Helpers for mapping selected nodes and errors to Markdown source lines. |
| `frontend/src/vite-env.d.ts` | Lets TypeScript understand Vite and CSS imports. |
| `frontend/src/graph/toFlow.test.ts` | Tests graph layout and mapping. |
| `frontend/src/editor/source.test.ts` | Tests Markdown selection and source helpers. |
| `frontend/e2e/editor.spec.ts` | Browser tests for parsing, source highlighting, invalid drafts, and refresh behavior. |

## Build files and examples

| File | What it does |
| --- | --- |
| `frontend/package.json` | npm dependencies and commands such as `npm run dev`, `npm test`, and `npm run build`. |
| `frontend/package-lock.json` | Locks npm dependency versions so team members install the same packages. |
| `frontend/vite.config.ts` | Tells Vite to compile assets into `backend/editor/static/editor/dist/`. |
| `frontend/tsconfig.json` | TypeScript compiler settings. |
| `frontend/playwright.config.ts` | Browser-test settings. |
| `frontend/scripts/update-fixture.mjs` | Helper for updating the example graph fixture. |
| `backend/editor/static/editor/dist/` | Generated frontend JavaScript, CSS, and manifest; rebuilt by Vite rather than edited directly. |
| `fixtures/merchant.md` | Example dialogue loaded into a new draft. |
| `fixtures/merchant.graph.json` | Expected graph output for that example. |
| `.gitignore` | Keeps local and generated files out of Git. |
| `THIRD_PARTY_NOTICES.md` | Third-party license notices. |

## Where to start for common changes

- **Changing Markdown syntax:** Start with `stub_parser.py`, then update parser tests and Markdown-editing helpers.
- **Adding a node field:** Check `graph.py`, `contract.ts`, `main.tsx`, and `patchNode.ts` so it survives both directions.
- **Changing node appearance:** Use `DialogueNode.tsx` and `dialogue-graph.css`.
- **Changing connection behavior or layout:** Look at `DialogueGraph.tsx`, `toFlow.ts`, `LoopEdge.tsx`, and `graphEdits.ts`.
- **Changing saving or validation:** Start with `views.py`, `validator.py`, and the Django tests.

One thing to watch: the project currently represents dialogue in two forms, Markdown and graph data. Changes need to stay consistent across the Python graph payload, TypeScript types, and the code that writes graph edits back to Markdown.
