from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash, current_app,
)

from app.repositories.usuario_repository import UsuarioRepository
from app.services.auth_service import AuthService
from app.utils.csrf import generate_csrf_token, validate_csrf_token
from app.utils.logger import log_auth_success, log_auth_failure, log_critical_action
from app.utils.validators import (
    validar_correo,
    validar_telefono,
    validar_texto_seguro,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _auth_service() -> AuthService:
    return AuthService(UsuarioRepository())


@auth_bp.route("/register", methods=["GET"])
def register_form():
    if session.get("usuario_id"):
        rol = session.get("usuario_rol")
        if rol == "Administrador":
            return redirect(url_for("admin.dashboard"))
        elif rol in ("Supervisor", "Tecnico", "Técnico", "Operador"):
            return redirect(url_for("supervisor.dashboard"))
        return redirect(url_for("public.index"))

    token = generate_csrf_token()
    return render_template("auth/register.html", csrf_token=token, datos={})


@auth_bp.route("/register", methods=["POST"])
def register_submit():
    # Validación CSRF
    if not validate_csrf_token(request.form.get("csrf_token")):
        log_auth_failure("desconocido", "CSRF_invalido_o_expirado")
        flash("Su sesión expiró. Intente de nuevo.", "danger")
        return redirect(url_for("auth.register_form"))

    raw_nombre = request.form.get("nombre") or ""
    raw_correo = request.form.get("correo") or ""
    raw_telefono = request.form.get("telefono") or ""
    password = request.form.get("password") or ""

    # 1. Campos obligatorios
    if not raw_nombre.strip() or not raw_correo.strip() or not password:
        flash("Nombre, correo y contraseña son obligatorios.", "danger")
        return redirect(url_for("auth.register_form"))

    # 2. Validación de nombre
    es_val_nombre, nombre, err_nombre = validar_texto_seguro(raw_nombre, "nombre", min_len=3, max_len=100)
    if not es_val_nombre or not nombre:
        flash(err_nombre or "El nombre no es válido.", "danger")
        return redirect(url_for("auth.register_form"))

    # 3. Validación de formato de correo
    es_val_correo, correo, err_correo = validar_correo(raw_correo)
    if not es_val_correo or not correo:
        flash(err_correo or "Formato de correo inválido.", "danger")
        return redirect(url_for("auth.register_form"))

    # 4. Validación de teléfono (opcional pero debe tener 10 dígitos numéricos si se suministra)
    es_val_tel, telefono, err_tel = validar_telefono(raw_telefono, opcional=True)
    if not es_val_tel:
        flash(err_tel or "El formato del teléfono es inválido.", "danger")
        return redirect(url_for("auth.register_form"))

    # 5. Longitud mínima de contraseña
    if len(password) < 6:
        flash("La contraseña debe tener al menos 6 caracteres.", "danger")
        return redirect(url_for("auth.register_form"))

    # 6. Verificación de correo no duplicado
    service = _auth_service()
    if service.existe_correo(correo):
        flash("El correo electrónico ya se encuentra registrado.", "warning")
        return redirect(url_for("auth.register_form"))

    # 7. Persistencia segura (contraseña cifrada con PBKDF2/SHA256)
    exito, id_usuario, err_msg = service.registrar_usuario(
        nombre=nombre,
        correo=correo,
        password=password,
        telefono=telefono,
        rol="Ciudadano",
    )
    if not exito:
        flash(err_msg or "No se pudo registrar la cuenta.", "danger")
        return redirect(url_for("auth.register_form"))

    log_critical_action("REGISTRO_USUARIO", f"Usuario {correo} registrado exitosamente con ID {id_usuario}")
    flash("¡Registro exitoso! Ya puedes iniciar sesión con tus credenciales.", "success")
    return redirect(url_for("auth.login_form"))


@auth_bp.route("/login", methods=["GET"], endpoint="login")
@auth_bp.route("/login", methods=["GET"], endpoint="login_form")
def login_form():
    if session.get("usuario_id"):
        rol = session.get("usuario_rol")
        if rol == "Administrador":
            return redirect(url_for("admin.dashboard"))
        elif rol in ("Supervisor", "Tecnico", "Técnico", "Operador"):
            return redirect(url_for("supervisor.dashboard"))
        return redirect(url_for("public.index"))

    token = generate_csrf_token()
    return render_template("auth/login.html", csrf_token=token)


@auth_bp.route("/login", methods=["POST"])
def login_submit():
    # CSRF
    if not validate_csrf_token(request.form.get("csrf_token")):
        log_auth_failure("desconocido", "CSRF_invalido_o_expirado")
        flash("Su sesión expiró. Intente de nuevo.", "danger")
        return redirect(url_for("auth.login_form"))

    raw_correo = request.form.get("correo") or ""
    password = request.form.get("password") or ""

    # Validación de formato con validators centralizados
    if not raw_correo.strip() or not password:
        log_auth_failure(raw_correo.strip() or "vacio", "credenciales_incompletas")
        flash("Correo y contraseña son obligatorios.", "danger")
        return redirect(url_for("auth.login_form"))

    es_valido, correo, err_correo = validar_correo(raw_correo)
    if not es_valido or not correo:
        log_auth_failure(raw_correo.strip(), "formato_correo_invalido")
        flash(err_correo or "Formato de correo inválido.", "danger")
        return redirect(url_for("auth.login_form"))

    usuario, motivo = _auth_service().authenticate(correo, password)

    if usuario is None:
        log_auth_failure(correo, motivo or "credenciales_erroneas")
        if motivo == "usuario_inactivo":
            flash("Su cuenta está inactiva. Contacte a CMAS.", "warning")
        else:
            # Mensaje genérico: no revela si el correo existe.
            flash("Correo o contraseña incorrectos.", "danger")
        return redirect(url_for("auth.login_form"))

    # Sesión segura
    session.clear()
    session.permanent = True
    session["usuario_id"] = usuario.id_usuario
    session["usuario_nombre"] = usuario.nombre
    session["usuario_rol"] = usuario.rol
    session["usuario_correo"] = usuario.correo

    # Regeneramos CSRF tras login exitoso (previene fixation)
    generate_csrf_token(force=True)

    # Registrar evento de auditoría sin exponer contraseñas
    log_auth_success(correo=usuario.correo, id_usuario=usuario.id_usuario, rol=usuario.rol)

    # Redirección inteligente post-login según rol
    if usuario.rol == "Administrador":
        return redirect(url_for("admin.dashboard"))
    elif usuario.rol in ("Supervisor", "Tecnico", "Técnico", "Operador"):
        return redirect(url_for("supervisor.dashboard"))
    else:
        return redirect(url_for("public.index"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    if not validate_csrf_token(request.form.get("csrf_token")):
        flash("Acción no permitida.", "danger")
        return redirect(url_for("auth.login_form"))

    u_id = session.get("usuario_id")
    u_rol = session.get("usuario_rol")
    if u_id:
        log_critical_action("CIERRE_SESION", f"Usuario {u_id} cerró sesión", usuario_id=u_id, rol=u_rol)

    session.clear()
    flash("Sesión cerrada correctamente.", "success")
    return redirect(url_for("auth.login_form"))


@auth_bp.route("/panel", methods=["GET"])
def panel():
    # Placeholder mínimo: NO es el dashboard de fases posteriores.
    from app.auth.decorators import require_login
    # Chequeo inline para no decorar y evitar imports circulares.
    if not session.get("usuario_id"):
        flash("Debe iniciar sesión para continuar.", "warning")
        return redirect(url_for("auth.login_form"))

    return render_template(
        "panel.html",
        nombre=session.get("usuario_nombre"),
        rol=session.get("usuario_rol"),
        csrf_token=generate_csrf_token(),
    )