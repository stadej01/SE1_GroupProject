# US-12 Starting Node Tests

These Playwright tests cover the starting-node workflow in the editor:

- A graph with no selected starting node displays a warning.
- Selecting a node marks it as `START` and the selection survives saving and reloading.
- More than one starting node can be selected.

## Run

From the `frontend` directory, install the Node dependencies if needed and make sure Django's Python dependencies are available. The Playwright config starts the Django test server automatically.

Install Playwright's Chromium browser once if it is not already installed:

```bash
npx playwright install chromium
```

Run only the US-12 tests:

```bash
npm run test:e2e -- e2e/us12-starting-node
```

If using an installed Chrome instead of Playwright's Chromium, set `CHROMIUM_EXECUTABLE_PATH` to its executable path. For example, on macOS:

```bash
CHROMIUM_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" npm run test:e2e -- e2e/us12-starting-node
```