# Graph editing V3

- Delete connections: select a graph edge or choose one from the Connections dropdown, then click Delete connection. Deletions update the pending Markdown buffer and synchronize when Parse is pressed.
- Selected nodes keep their original accent and show a yellow outline.
- From/To inputs support typing and native datalist suggestions (browser-dependent filtering). The node ID must match an existing node exactly.
- Parser diagnostics include clickable line numbers when the parser knows the source line. Some request-level errors have no source line.

## macOS
Terminal 1:
```sh
cd frontend
npm install
npm run dev
```
Terminal 2:
```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```
Visit http://127.0.0.1:8000/.

## Verification status
Static source changes inspected. Complete npm build / Django test run could not be completed in the authoring environment (npm install timed out; Django not installed). Run `npx tsc --noEmit` and `npm run build` locally after `npm install`.
