import json
from pathlib import Path
from uuid import uuid4
from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from dialogue_graph import GraphValidationError, build_graph, parse_markdown_to_ast
from .assets import frontend_assets
from .models import Draft

MAX_SOURCE_CHARS = 200_000
DEMO_SOURCE = Path(__file__).resolve().parents[2] / "fixtures" / "merchant.md"

def _error(message, status=400):
    return JsonResponse({"ok": False, "diagnostics": [
        {"severity": "error", "message": message}]}, status=status)

def _payload(request):
    if request.content_type != "application/json":
        return None, _error("Send an application/json request.", 415)
    try:
        value = json.loads(request.body)
    except RequestDataTooBig:
        return None, _error("Request is too large.", 413)
    except (ValueError, UnicodeDecodeError):
        return None, _error("Request body is not valid JSON.")
    if not isinstance(value, dict) or not isinstance(value.get("markdown_source"), str):
        return None, _error("markdown_source must be a string.")
    if len(value["markdown_source"]) > MAX_SOURCE_CHARS:
        return None, _error(f"Markdown must be at most {MAX_SOURCE_CHARS:,} characters.", 413)
    try:
        value["markdown_source"].encode("utf-8")
    except UnicodeEncodeError:
        return None, _error("Markdown must contain valid Unicode text.")
    return value, None

@never_cache
@ensure_csrf_cookie
@require_GET
def index(request):
    owner_key = request.session.get("draft_owner")
    if owner_key is None:
        owner_key = str(uuid4())
        request.session["draft_owner"] = owner_key
    draft, _ = Draft.objects.get_or_create(owner_key=owner_key,
        defaults={"markdown_source": DEMO_SOURCE.read_text(encoding="utf-8")})
    return render(request, "editor/index.html", {"markdown_source": draft.markdown_source,
        "revision": draft.revision, "assets": frontend_assets()})

@never_cache
@require_POST
def sync(request):
    payload, error = _payload(request)
    if error is not None:
        return error
    try:
        graph = build_graph(parse_markdown_to_ast(payload["markdown_source"]))
    except GraphValidationError as exc:
        return JsonResponse({"ok": False, "diagnostics": exc.diagnostics}, status=422)
    return JsonResponse({"ok": True, "graph": graph, "diagnostics": []})

@never_cache
@require_http_methods(["PUT"])
def save(request):
    payload, error = _payload(request)
    if error is not None:
        return error
    revision = payload.get("revision")
    if type(revision) is not int or revision < 0:
        return _error("revision must be a nonnegative integer.")
    owner_key = request.session.get("draft_owner")
    if owner_key is None:
        return _error("Your session expired. Copy your draft before reloading the page.", 409)
    # Atomic comparison prevents two tabs from silently overwriting each other.
    updated = Draft.objects.filter(owner_key=owner_key, revision=revision).update(
        markdown_source=payload["markdown_source"], revision=revision + 1, updated_at=timezone.now())
    if not updated:
        return _error("The saved draft changed in another tab. Copy your edits before reloading.", 409)
    # Saving deliberately does not parse: malformed and empty drafts remain editable.
    return JsonResponse({"ok": True, "saved": True, "revision": revision + 1})

def csrf_failure(request, reason=""):
    return _error("Security token expired or missing. Copy your edits before reloading.", 403)
