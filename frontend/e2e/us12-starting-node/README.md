# US-12 Starting Node Tests

These Playwright tests cover the starting-node workflow in the editor:

- A graph with no selected starting node displays a warning.
- Selecting a node marks it as `START` and the selection survives saving and reloading.
- More than one starting node can be selected.

## macOS

Run these commands from the repository root. Setup commands are only needed once. Keep the Python virtual environment active while running Playwright; its config starts the Django test server automatically.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd ../frontend
npm ci
npx playwright install chromium
npm run test:e2e -- e2e/us12-starting-node
```

## Windows (PowerShell)

Run these commands from the repository root. Setup commands are only needed once. If PowerShell blocks virtual-environment activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate again.

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd ..\frontend
npm ci
npx playwright install chromium
npm run test:e2e -- e2e/us12-starting-node
```

If the `py` launcher is unavailable, use `python -m venv .venv` instead.

## Other Commands

Run all browser tests from `frontend`:

```bash
npm run test:e2e
```

Run only the US-12 tests again:

```bash
npm run test:e2e -- e2e/us12-starting-node
```