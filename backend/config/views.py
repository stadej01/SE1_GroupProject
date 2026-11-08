"""Shared service endpoints and CSRF responses."""

from django.http import JsonResponse
from django.views.csrf import csrf_failure as default_csrf_failure
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_safe

from accounts.token_cookie import use_token_user
from editor.views import sync as editor_sync


def diagnostic_response(message, status):
    return JsonResponse(
        {"ok": False, "diagnostics": [{"severity": "error", "message": message}]},
        status=status,
    )


@never_cache
@csrf_exempt
def sync(request):
    # Check the token cookie first so an expired login returns JSON 401 even without a CSRF token.
    # Signed-in requests still pass the full CSRF check before parsing.
    if not use_token_user(request).is_authenticated:
        return diagnostic_response("Please log in before parsing.", 401)
    return csrf_protect(editor_sync)(request)


def csrf_failure(request, reason=""):
    if (
        request.content_type == "application/json"
        or "application/json" in request.headers.get("Accept", "")
    ):
        return diagnostic_response(
            "Security token expired or missing. Copy your edits before reloading.", 403
        )
    return default_csrf_failure(request, reason=reason)


@require_safe
def health(request):
    return JsonResponse({"status": "ok"})
