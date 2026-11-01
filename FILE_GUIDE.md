# Current demo settings (sprint merge)

There are now two independent Django settings modules: `backend/config/settings.py` is the local SQLite dialogue editor, and `backend/config/settings_neon.py` is the Neon accounts/teams demo. `backend/config/urls.py` and `urls_neon.py` keep their route maps separate. `settings_auth_test.py` exercises accounts and teams with local SQLite instead of Neon. See the README for startup commands.

---

# File guide

This is a quick reference for the files we're most likely to touch while working on the dialogue editor. It covers our code and configuration, not installed packages, generated caches, or every Django boilerplate file.

## Django backend

| File | What it does |
| --- | --- |
| `backend/manage.py` | Runs Django commands such as `runserver`, `migrate`, and `test`. |
| `backend/requirements.txt` | Lists the pinned Django, django-environ, and psycopg dependencies needed by both demos. |
| `backend/config/settings.py` | Sets up Django, SQLite, installed apps, templates, security settings, and static files for local development. |
| `backend/config/urls.py` | Sends incoming URLs to the editor app. |
| `backend/config/settings_neon.py` | Separate settings for the accounts/teams demo using Neon PostgreSQL. |
| `backend/config/urls_neon.py` | Routes the accounts/teams demo to Django admin and the health endpoint. |
| `backend/config/settings_auth_test.py` | Uses an in-memory SQLite test database to test account/team functionality without Neon. |
| `backend/accounts/models.py` | Custom email-based user model for the accounts demo. |
| `backend/teams/models.py` | Team and team membership models. |
| `backend/accounts/tests.py` / `teams/tests.py` | Tests authentication, user admin, and team membership. |
| `backend/config/asgi.py` / `wsgi.py` | Standard Django entry points for hosting; we don't usually need to edit them for local development. |
| `backend/editor/urls.py` | Defines the page (`/`), parse (`/sync`), and save (`/save`) routes. |
| `backend/editor/views.py` | Handles loading the editor, validating/parsing Markdown, and saving drafts. Invalid drafts can still be saved. |
| `backend/editor/models.py` | Defines `Draft`, which stores a Markdown draft and revision number for each browser session. |
| `backend/editor/migrations/0001_initial.py` | Creates the draft table when you run migrations. |
| `backend/editor/assets.py` | Finds the JavaScript and CSS files built by Vite so Django can load them. |
| `backend/editor/templates/editor/index.html` | HTML layout for the two-panel page and buttons; React mounts the graph into this page. |
| `backend/editor/tests.py` | Django tests for the page, parse/save endpoints, draft behavior, and request handling. |

## Parsing and graph data

| File | What it does |
| --- | --- |
| `backend/dialogue_graph/stub_parser.py` | Temporary Markdown parser. Recognizes headers, dialogue lines, choices, jumps, conditions, and metadata; records source line numbers. This is what we'll eventually replace with Lark. |
| `backend/dialogue_graph/validator.py` | Checks parser errors, duplicate IDs, blank choice labels, and links to missing nodes. |
| `backend/dialogue_graph/graph.py` | Converts validated parser output into the nodes and edges sent to React Flow. |
| `backend/dialogue_graph/__init__.py` | Exposes the parser/graph functions used by the Django views. |
| `backend/dialogue_graph/__main__.py` | Command-line entry point for working with the parser outside Django. |
| `backend/tests/test_graph.py` | Unit tests for parsing, validation, source lines, and graph connections. |

## React frontend

| File | What it does |
| --- | --- |
| `frontend/src/main.tsx` | Main editor code. Makes Django API requests, manages pending graph edits, and wires up the toolbar, selection, parsing, and saving. |
| `frontend/src/editor.css` | Styles for the editor page, toolbar, panels, and dialogs. |
| `frontend/src/components/DialogueGraph.tsx` | Renders and manages the React Flow canvas, including node selection, dragging, and connections. |
| `frontend/src/components/DialogueNode.tsx` | Draws one node, including its ID, all dialogue lines, color, and selection highlight. |
| `frontend/src/components/LoopEdge.tsx` | Custom drawing for loop/back connections. |
| `frontend/src/components/dialogue-graph.css` | Styles specific to the graph nodes and connections. |
| `frontend/src/graph/contract.ts` | TypeScript definitions for the graph payload returned by Django. This has to stay in step with the Python graph output. |
| `frontend/src/graph/toFlow.ts` | Turns the graph payload into React Flow nodes/edges and calculates layouts and routes. |
| `frontend/src/editor/graphEdits.ts` | Adds or removes nodes and connections in the pending Markdown text. |
| `frontend/src/editor/patchNode.ts` | Updates a node's dialogue and metadata in Markdown while keeping its connections and unrelated lines. |
| `frontend/src/editor/source.ts` | Helpers for mapping selected nodes/errors to Markdown source lines. |
| `frontend/src/vite-env.d.ts` | Lets TypeScript understand Vite and CSS imports. |
| `frontend/src/graph/toFlow.test.ts` | Tests graph layout and mapping. |
| `frontend/src/editor/source.test.ts` | Tests Markdown selection/source helpers. |
| `frontend/e2e/editor.spec.ts` | Browser tests for parsing, source highlighting, invalid drafts, and refresh behavior. |

## Build files and examples

| File | What it does |
| --- | --- |
| `frontend/package.json` | npm dependencies and commands like `npm run dev`, `npm test`, and `npm run build`. |
| `frontend/package-lock.json` | Locks npm dependency versions so team members install the same packages. |
| `frontend/vite.config.ts` | Tells Vite to compile assets into `backend/editor/static/editor/dist/`. |
| `frontend/tsconfig.json` | TypeScript compiler settings. |
| `frontend/playwright.config.ts` | Browser-test settings. |
| `frontend/scripts/update-fixture.mjs` | Helper for updating the example graph fixture. |
| `backend/editor/static/editor/dist/` | Generated frontend JavaScript, CSS, and manifest. Rebuilt by Vite; normally don't edit these files directly. |
| `fixtures/merchant.md` | The example dialogue loaded into a new draft. |
| `fixtures/merchant.graph.json` | Expected graph output for that example. |
| `.gitignore` | Keeps local/generated files out of Git. |
| `THIRD_PARTY_NOTICES.md` | Third-party license notices. |

## Where to start for common changes

- **Changing Markdown syntax:** Start with `stub_parser.py`, then update the parser tests and any Markdown-editing helpers.
- **Adding a node field:** Check `graph.py`, `contract.ts`, `main.tsx`, and `patchNode.ts` so it survives both directions.
- **Changing node appearance:** Use `DialogueNode.tsx` and `dialogue-graph.css`.
- **Changing connection behavior or layout:** Look at `DialogueGraph.tsx`, `toFlow.ts`, `LoopEdge.tsx`, and `graphEdits.ts`.
- **Changing saving or validation:** Start with `views.py`, `validator.py`, and the Django tests.

One thing to watch: there are currently two different representations of the same dialogue (Markdown and graph data). Changes need to stay consistent across the Python graph payload, the TypeScript types, and the code that writes edits back into Markdown.
