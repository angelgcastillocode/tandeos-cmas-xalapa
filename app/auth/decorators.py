from functools import wraps
from typing import Iterable
from flask import session, redirect, url_for, flash, abort


def require_login(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("usuario_id"):
            flash("Debe iniciar sesión para continuar.", "warning")
            return redirect(url_for("auth.login_form"))
        return view(*args, **kwargs)
    return wrapper


# Alias convencional
login_required = require_login


def require_role(*roles: Iterable[str]):
    """Exige que el usuario tenga al menos uno de los roles indicados."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not session.get("usuario_id"):
                flash("Debe iniciar sesión para continuar.", "warning")
                return redirect(url_for("auth.login_form"))
            if session.get("usuario_rol") not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapper
    return decorator