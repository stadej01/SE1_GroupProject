# Delivery validation

Checked on October 28, 2026 with Python 3.12.14, Django 5.2.18, Node 24.22.1,
TypeScript 5.9.3, and Vite 7.3.7. Installed frontend versions are recorded in
`frontend/package-lock.json`.

| Check | Result |
| --- | --- |
| Django and parser tests | 29 passed |
| TypeScript graph and source-range tests | 12 passed |
| Playwright browser tests against Django | 3 passed |
| TypeScript check and production Vite build | Passed |
| Django system checks | No issues |
| Migration consistency check | No changes detected |
| Django `collectstatic` | All 3 generated static files collected |
| Desktop and mobile rendering inspection | No page overflow at widths 1440 and 390 |

The 44 tests cover valid graph generation, syntax and structural error blocking,
source spans, ordered AST content, session-isolated draft saving, empty/invalid
draft persistence, stale revision conflicts, CSRF, malformed requests, template
escaping, edge styles, loop detection/clearance, long graph traversal, Unicode
source selection, dialogue-only refreshes, and delayed-response suppression.

Browser tests used a local Chromium executable through
`CHROMIUM_EXECUTABLE_PATH`; the standard Playwright browser download was not
available in the build environment. The application itself runs without any CDN
assets or externally hosted JavaScript.

Not verified or implemented: production deployment, game execution, Lark syntax,
project-wide references across files, complete JSON export, arbitrary obstacle
routing, or interactive rendering of game-scale graphs. The 12,000-node unit test
exercises pure mapping and layout functions only.
