from flask import Flask
from config.config import Config


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Repositorios / DB
    from app.repositories.db import close_db
    app.teardown_appcontext(close_db)

    # Blueprints
    from app.auth.routes import auth_bp
    app.register_blueprint(auth_bp)

    from app.public.routes import public_bp
    app.register_blueprint(public_bp)

    from app.routes.consulta_routes import consulta_bp
    app.register_blueprint(consulta_bp)

    from app.routes.reporte_routes import reporte_bp
    app.register_blueprint(reporte_bp)

    from app.routes.supervisor_routes import supervisor_bp
    app.register_blueprint(supervisor_bp)

    from app.routes.admin_routes import admin_bp
    app.register_blueprint(admin_bp)

    from app.routes.notification_routes import notification_bp
    app.register_blueprint(notification_bp)

    # Sistema de Logging y Auditoría
    from app.utils.logger import setup_logging
    setup_logging(app)

    # Manejo centralizado de errores corporativos
    from app.errors import register_error_handlers
    register_error_handlers(app)

    # Inyección de contexto global para Jinja2 (current_user y csrf_token)
    from flask import session
    from app.utils.csrf import generate_csrf_token

    class AnonymousUser:
        is_authenticated = False
        is_anonymous = True
        id_usuario = None
        nombre = None
        correo = None
        rol = None

    class AuthenticatedUser:
        is_authenticated = True
        is_anonymous = False

        def __init__(self, id_usuario, nombre=None, rol=None, correo=None):
            self.id_usuario = id_usuario
            self.nombre = nombre or ""
            self.rol = rol or "Ciudadano"
            self.correo = correo or ""

    @app.context_processor
    def inject_auth_context():
        user_id = session.get("usuario_id")
        if user_id:
            user = AuthenticatedUser(
                id_usuario=user_id,
                nombre=session.get("usuario_nombre"),
                rol=session.get("usuario_rol"),
                correo=session.get("usuario_correo"),
            )
        else:
            user = AnonymousUser()

        return {
            "current_user": user,
            "csrf_token": generate_csrf_token(),
        }

    # Cabeceras corporativas de seguridad HTTP
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    return app