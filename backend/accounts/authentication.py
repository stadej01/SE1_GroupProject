from rest_framework.authentication import (
    BaseAuthentication,
    SessionAuthentication,
    get_authorization_header,
)
from rest_framework.exceptions import AuthenticationFailed

from .token_cookie import user_from_cookie
from .tokens import InvalidToken, user_from_token


class SessionLoginAuthentication(SessionAuthentication):
    """Session login that answers unauthenticated API requests with 401."""

    def authenticate_header(self, request):
        return "Session"


class JWTAuthentication(BaseAuthentication):
    """Signs a request in from an `Authorization: Bearer <token>` header."""

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != b"bearer":
            return None  # No token sent, so let the next class try.
        if len(parts) != 2:
            raise AuthenticationFailed("Invalid Authorization header.")
        try:
            user = user_from_token(parts[1].decode())
        except (InvalidToken, UnicodeError):
            raise AuthenticationFailed("Invalid or expired token.")
        return (user, None)

    def authenticate_header(self, request):
        return "Bearer"


class JWTCookieAuthentication(SessionAuthentication):
    """Signs a browser request in from the httpOnly token cookie.

    Writes must carry the CSRF token, as with session login. A request with a
    Bearer header is handled by JWTAuthentication first and skips this check.
    """

    def authenticate(self, request):
        user = user_from_cookie(request)
        if user is None:
            return None
        self.enforce_csrf(request)
        return (user, None)

    def authenticate_header(self, request):
        return "Bearer"
