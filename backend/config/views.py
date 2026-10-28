"""Application health endpoint."""

from django.http import JsonResponse
from django.views.decorators.http import require_safe


@require_safe
def health(request):
    return JsonResponse({"status": "ok"})
