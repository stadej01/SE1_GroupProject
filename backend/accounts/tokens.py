import datetime

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model

ALGORITHM = "HS256"


class InvalidToken(Exception):
    """The token is malformed, forged, expired, or belongs to no active user."""


def create_token(user):
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(user.pk),
        "iat": now,
        "exp": now + datetime.timedelta(seconds=settings.JWT_LIFETIME_SECONDS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def user_from_token(token):
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as error:
        raise InvalidToken("Invalid or expired token.") from error
    user = get_user_model().objects.filter(pk=payload["sub"], is_active=True).first()
    if user is None:
        raise InvalidToken("Invalid or expired token.")
    return user