import secrets
from flask import session

_CSRF_KEY = "_csrf_token"
_TOKEN_BYTES = 32


def generate_csrf_token(force: bool = False) -> str:
    """
    Devuelve el token CSRF de la sesión actual.
    Si no existe o 'force' es True, genera uno nuevo.
    """
    if force or _CSRF_KEY not in session:
        session[_CSRF_KEY] = secrets.token_urlsafe(_TOKEN_BYTES)
    return session[_CSRF_KEY]


def validate_csrf_token(token: str) -> bool:
    """Compara de forma timing-safe el token recibido con el de la sesión."""
    expected = session.get(_CSRF_KEY)
    if not expected or not token:
        return False
    return secrets.compare_digest(str(expected), str(token)) 