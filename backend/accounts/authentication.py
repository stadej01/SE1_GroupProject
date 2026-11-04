from rest_framework.authentication import SessionAuthentication


class SessionLoginAuthentication(SessionAuthentication):
    """Session login that answers unauthenticated API requests with 401."""

    def authenticate_header(self, request):
        return "Session"
