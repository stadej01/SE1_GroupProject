"""Keeps the sign-in token in an httpOnly cookie for the browser pages."""

from functools import wraps

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.views import redirect_to_login
from django.middleware.csrf import rotate_token
from rest_framework.authentication import CSRFCheck

from .tokens import InvalidToken, user_from_token


def _cookie_options():
    return {"httponly": True, "samesite": "Lax", "secure": not settings.DEBUG}


def set_token_cookie(request, response, token):
    """Stores the token for the browser and starts a new CSRF token, as a login should."""
    response.set_cookie(
        settings.JWT_COOKIE_NAME,
        token,
        max_age=settings.JWT_LIFETIME_SECONDS,
        **_cookie_options(),
    )
    rotate_token(request)
    return response


def has_valid_csrf_token(request):
    """True when the request carries this site's CSRF token, as our login page does.

    Another site cannot read that token, so it cannot sign a visitor in to its own account.
    """
    check = CSRFCheck(lambda request: None)
    check.process_request(request)
    return check.process_view(request, None, (), {}) is None


def clear_token_cookie(response):
    response.set_cookie(settings.JWT_COOKIE_NAME, "", max_age=0, **_cookie_options())
    return response


def user_from_cookie(request):
    """Returns the active user named by a valid token cookie, or None."""
    token = request.COOKIES.get(settings.JWT_COOKIE_NAME)
    if not token:
        return None
    try:
        return user_from_token(token)
    except InvalidToken:
        return None


def use_token_user(request):
    """Lets the token cookie, not the Django admin session, decide who is signed in."""
    request.user = user_from_cookie(request) or AnonymousUser()
    return request.user


def token_login_required(view):
    """Sends visitors without a valid token cookie to the login page."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not use_token_user(request).is_authenticated:
            return redirect_to_login(request.get_full_path())
        return view(request, *args, **kwargs)

    return wrapper
