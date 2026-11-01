# Dialogue Editor

This is our dialogue editor prototype for the SE1 group project. The idea is to write game dialogue in Markdown and see it as a node graph. We can also edit nodes and connections in the graph, then sync those changes back to the Markdown.

The app uses Django for the server and React Flow for the graph. Django serves the page, so there isn't a separate React website to open. Vite just compiles the frontend files that Django uses.

This is still a prototype. The Markdown parser supports basic dialogue, choices, jumps, and some metadata, but it isn't the full dialogue language we want for quests, items, characters, and variables.

## What you need

- Python 3.10 or newer
- Node.js 22.12 or newer (includes npm)
- A terminal: Terminal on macOS or PowerShell on Windows

Unzip the project and open a terminal in the folder containing `frontend` and `backend`. The name of that folder doesn't matter.

## Run on macOS

Open **two Terminal windows** in the project folder.

**Terminal 1 — frontend**

```bash
cd frontend
npm install
npm run dev
```

Keep this open. `npm run dev` runs `vite build --watch`, which rebuilds the frontend when we change the code. It doesn't give you a separate web address.

**Terminal 2 — Django**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Now open **http://127.0.0.1:8000/**.

## Run on Windows

Use **two PowerShell windows** in the project folder. You can open the folder in VS Code and use two terminals there.

**Terminal 1 — frontend**

```powershell
cd frontend
npm install
npm run dev
```

**Terminal 2 — Django**

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open **http://127.0.0.1:8000/** when Django starts.

If PowerShell won't activate the virtual environment, run these commands in Terminal 2:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

If Windows doesn't recognize `py`, use `python -m venv .venv` instead.

## Starting it again

You only need to create the virtual environment and install dependencies the first time (or when dependencies change).

On **macOS**, run:

```bash
# Terminal 1 (from the project folder)
cd frontend
npm run dev
```

```bash
# Terminal 2 (from the project folder)
cd backend
source .venv/bin/activate
python manage.py runserver
```

On **Windows**, run:

```powershell
# Terminal 1 (from the project folder)
cd frontend
npm run dev
```

```powershell
# Terminal 2 (from the project folder)
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

Press **Ctrl+C** in either terminal to stop its process. If we change frontend dependencies, run `npm install` again. After new Django migrations are added, run `python manage.py migrate` again.

## Using the editor

1. Write or edit Markdown on the left, then click **Parse Markdown** to build the graph.
2. Click a node to find its source in Markdown. You can also edit its speaker, dialogue, audience, and extra fields.
3. Use **+ New node** to add a node. To connect nodes, drag between their handles or use the **From**, **To**, and **Type** controls above the graph.
4. Select a connection and click **Delete connection** to remove it.
5. Changes made in the graph appear there immediately, but **the Markdown doesn't change until you click Parse Markdown**. Then click **Save draft** to save the updated Markdown.
6. You can save Markdown drafts even when they contain errors. Invalid Markdown won't generate a graph, and the error messages will show line numbers when available.
7. The layout controls let you switch between horizontal and vertical views and rotate connection labels.

A small example:

```markdown
# Node_Greeting
<!-- category: shop, color: blue -->
Merchant: Welcome, traveler.
Merchant: What can I do for you?
* "Browse the shop" -> Node_Shop

# Node_Shop
Merchant: Take your time.
<<jump: Node_Greeting>>
```

There's a larger example in `fixtures/merchant.md`.

## Where the code is

| File or folder | What it's for |
| --- | --- |
| `backend/editor/views.py` | The Django page, parse endpoint, and draft-saving endpoint. |
| `backend/editor/models.py` | The database model for saved Markdown drafts. |
| `backend/dialogue_graph/stub_parser.py` | Reads the current Markdown format and builds a basic syntax tree. |
| `backend/dialogue_graph/validator.py` | Checks node IDs, links, and parsing errors. |
| `backend/dialogue_graph/graph.py` | Turns the parsed data into nodes and connections for the frontend. |
| `frontend/src/main.tsx` | Main editor logic: parsing, saving, editing nodes, and graph controls. |
| `frontend/src/components/DialogueGraph.tsx` | Sets up the interactive React Flow graph. |
| `frontend/src/components/DialogueNode.tsx` | Displays each dialogue node and its lines. |
| `frontend/src/graph/toFlow.ts` | Calculates graph positions and connection routes. |
| `frontend/src/editor/` | Code that applies node and connection edits to Markdown. |
| `fixtures/merchant.md` | Example dialogue for testing. |

For a more complete file-by-file breakdown, see **[FILE_GUIDE.md](FILE_GUIDE.md)**.

## Tests

From `backend` (with the Python virtual environment active):

```bash
python manage.py test
python -m unittest discover -s tests
```

From `frontend`:

```bash
npm run typecheck
npm test
npm run build
```

Browser tests are also available with `npm run test:e2e`; Playwright may need its browser dependencies installed first.

## If something isn't working

- **`requirements.txt` not found:** Run the pip command inside `backend`, not the project root.
- **`manage.py` not found:** You're probably not in `backend`.
- **Vite says `build --watch`:** That's normal. Open Django at port 8000, not Vite at 5173.
- **The page looks unchanged:** Check that the Vite build finished, then refresh the browser.
- **Port 8000 is already in use:** Stop the old server or run `python manage.py runserver 8001`.
- **TypeScript complains about CSS or Vite imports:** Run `npm install` inside `frontend`, then restart VS Code's TypeScript server. The project includes `src/vite-env.d.ts`.

## Still to do

The current parser is a temporary, line-based parser. We still need to replace it with the planned Lark implementation, finish the broader game dialogue model, and add JSON export. Node positions aren't permanently saved, and project-wide links across separate dialogue files aren't supported yet.

This configuration is for local development, not public deployment.
