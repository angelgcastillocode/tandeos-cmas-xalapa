"""
Rutas y Blueprint para el Módulo de Notificaciones y Alertas de CMAS Xalapa.
Incluye protección estricta de CSRF, autenticación de sesión, mitigación de IDOR y control de acceso.
"""

from functools import wraps
from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    request,
    session,
    url_for,
)

from app.services.notification_service import NotificationService
from app.utils.csrf import generate_csrf_token, validate_csrf_token
from app.utils.logger import log_critical_action
from app.utils.validators import (
    sanitizar_cadena,
    validar_entero_positivo,
    validar_limite_offset,
    validar_permiso_acceso,
)

notification_bp = Blueprint("notificaciones", __name__, url_prefix="/notificaciones")


def _get_service() -> NotificationService:
    return NotificationService()


def login_requerido(view_func):
    """Exige que el usuario tenga sesión activa."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("usuario_id"):
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({
                    "success": False,
                    "error": "No autorizado",
                    "mensaje": "Debe iniciar sesión para continuar.",
                }), 401
            flash("Debe iniciar sesión para continuar.", "warning")
            return redirect(url_for("auth.login_form"))
        return view_func(*args, **kwargs)
    return wrapper


def rol_requerido(*roles):
    """Exige que el usuario cuente con uno de los roles especificados."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if not session.get("usuario_id"):
                if request.is_json or request.headers.get("Accept") == "application/json":
                    return jsonify({"success": False, "error": "No autorizado"}), 401
                flash("Debe iniciar sesión para continuar.", "warning")
                return redirect(url_for("auth.login_form"))
            if session.get("usuario_rol") not in roles:
                if request.is_json or request.headers.get("Accept") == "application/json":
                    return jsonify({"success": False, "error": "Acceso denegado. Permisos insuficientes."}), 403
                abort(403)
            return view_func(*args, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# 1. Endpoints de Preferencias de Usuario (Con Protección IDOR)
# =============================================================================

@notification_bp.route("/preferencias", methods=["GET"])
@login_requerido
def obtener_preferencias():
    """Obtiene las preferencias de notificación del usuario en sesión protegiendo contra IDOR."""
    service = _get_service()
    id_usuario_sesion = session.get("usuario_id")
    rol_sesion = session.get("usuario_rol")

    id_usuario = id_usuario_sesion

    target_id = request.args.get("id_usuario")
    if target_id:
        es_val, parsed_target, _ = validar_entero_positivo(target_id, "id_usuario")
        if es_val and parsed_target:
            if rol_sesion in ("Administrador", "Supervisor"):
                id_usuario = parsed_target
            elif parsed_target != id_usuario_sesion:
                # Intento de IDOR por usuario estándar
                return jsonify({
                    "success": False,
                    "error": "Acceso No Autorizado",
                    "mensaje": "No cuenta con permisos para consultar preferencias de otros usuarios.",
                }), 403

    preferencias = service.obtener_preferencias(id_usuario)
    csrf_token = generate_csrf_token()

    return jsonify({
        "success": True,
        "preferencias": preferencias,
        "csrf_token": csrf_token,
    }), 200


@notification_bp.route("/preferencias", methods=["POST"])
@login_requerido
def actualizar_preferencias():
    """
    Actualiza las preferencias de notificación del usuario.
    Valida obligatoriamente el token CSRF y previene IDOR.
    """
    # 1. Validación estricta de CSRF
    token_csrf = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not token_csrf and request.is_json and request.json:
        token_csrf = request.json.get("csrf_token")

    if not validate_csrf_token(token_csrf):
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({
                "success": False,
                "error": "Token CSRF inválido o expirado.",
            }), 400
        flash("Token CSRF inválido o sesión expirada.", "danger")
        return redirect(url_for("notificaciones.obtener_preferencias"))

    # 2. Extracción de datos (compatible con Form y JSON)
    id_usuario_sesion = session.get("usuario_id")
    rol_sesion = session.get("usuario_rol")
    id_usuario = id_usuario_sesion
    target_id = None

    if request.is_json and request.json:
        data = request.json
        notif_email = bool(data.get("notif_email", False))
        notif_sms = bool(data.get("notif_sms", False))
        id_colonia = data.get("id_colonia")
        target_id = data.get("id_usuario")
    else:
        # En HTML checkboxes: presentes si marcados
        notif_email = "notif_email" in request.form or request.form.get("notif_email") in ("1", "true", "True")
        notif_sms = "notif_sms" in request.form or request.form.get("notif_sms") in ("1", "true", "True")
        id_colonia = request.form.get("id_colonia")
        target_id = request.form.get("id_usuario")

    if target_id is not None:
        es_val, parsed_target, _ = validar_entero_positivo(target_id, "id_usuario")
        if es_val and parsed_target:
            if rol_sesion in ("Administrador", "Supervisor"):
                id_usuario = parsed_target
            elif parsed_target != id_usuario_sesion:
                # Intento de IDOR bloqueado
                return jsonify({
                    "success": False,
                    "error": "Acceso No Autorizado",
                    "mensaje": "No cuenta con permisos para modificar preferencias de otros usuarios.",
                }), 403

    colonia_id_parsed = None
    if id_colonia:
        es_val_col, col_val, _ = validar_entero_positivo(id_colonia, "id_colonia")
        if es_val_col:
            colonia_id_parsed = col_val

    service = _get_service()
    try:
        resultado = service.actualizar_preferencias(
            id_usuario=id_usuario,
            notif_email=notif_email,
            notif_sms=notif_sms,
            id_colonia=colonia_id_parsed,
        )
        return jsonify({
            "success": True,
            "mensaje": "Preferencias de notificación actualizadas exitosamente.",
            "preferencias": resultado,
        }), 200
    except ValueError as err:
        return jsonify({"success": False, "error": str(err)}), 400


# =============================================================================
# 2. Endpoints de Consulta de Historial y Auditoría (IDOR Mitigado)
# =============================================================================

@notification_bp.route("/historial", methods=["GET"])
@login_requerido
def consultar_historial():
    """
    Consulta el historial de notificaciones.
    Los ciudadanos solo pueden ver sus propias alertas.
    Los roles administrativos pueden consultar globalmente o filtrar por usuario.
    """
    id_usuario_sesion = session.get("usuario_id")
    rol_sesion = session.get("usuario_rol")

    filtro_usuario = id_usuario_sesion
    raw_target = request.args.get("id_usuario")
    if raw_target:
        es_val, parsed_id, _ = validar_entero_positivo(raw_target, "id_usuario")
        if es_val and parsed_id:
            if rol_sesion in ("Administrador", "Supervisor"):
                filtro_usuario = parsed_id
            elif parsed_id != id_usuario_sesion:
                return jsonify({
                    "success": False,
                    "error": "Acceso No Autorizado",
                    "mensaje": "No cuenta con permisos para consultar el historial de otros usuarios.",
                }), 403
    elif rol_sesion in ("Administrador", "Supervisor"):
        filtro_usuario = None  # Ver global si no especifica

    canal = sanitizar_cadena(request.args.get("canal")) or None
    estado = sanitizar_cadena(request.args.get("estado")) or None
    tipo = sanitizar_cadena(request.args.get("tipo")) or None

    limite, offset = validar_limite_offset(
        request.args.get("limite"),
        request.args.get("offset"),
        max_limite=100,
        default_limite=50,
    )

    service = _get_service()
    historial = service.obtener_historial_usuario(
        id_usuario=filtro_usuario,
        canal=canal,
        estado=estado,
        tipo=tipo,
        limite=limite,
        offset=offset,
    )

    return jsonify({
        "success": True,
        "total": len(historial),
        "historial": historial,
    }), 200


@notification_bp.route("/<int:id_notificacion>/auditoria", methods=["GET"])
@login_requerido
def consultar_auditoria(id_notificacion: int):
    """Devuelve la bitácora histórica completa de transiciones de una notificación protegiendo IDOR."""
    es_val, parsed_id, err = validar_entero_positivo(id_notificacion, "id_notificacion")
    if not es_val or not parsed_id:
        return jsonify({"success": False, "error": err or "Identificador inválido."}), 400

    service = _get_service()
    notif = service._repo.obtener_notificacion_por_id(parsed_id)
    if not notif:
        return jsonify({"success": False, "error": "Notificación no encontrada."}), 404

    # Control de IDOR
    usuario_id_sesion = session.get("usuario_id")
    rol_sesion = session.get("usuario_rol")
    if not validar_permiso_acceso(usuario_id_sesion, rol_sesion, notif["id_usuario"]):
        return jsonify({
            "success": False,
            "error": "Acceso denegado. No tiene permisos sobre este recurso.",
        }), 403

    bitacora = service.obtener_auditoria_notificacion(parsed_id)
    return jsonify({
        "success": True,
        "id_notificacion": parsed_id,
        "bitacora": bitacora,
    }), 200


# =============================================================================
# 3. Endpoints Operativos de Cola y Motor de 24h (Administración / Cron)
# =============================================================================

@notification_bp.route("/cola/procesar", methods=["POST"])
@rol_requerido("Administrador", "Supervisor", "Operador")
def procesar_cola():
    """Despacha las notificaciones en estado 'Pendiente' en lotes controlados."""
    token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not token and request.is_json and request.json:
        token = request.json.get("csrf_token")

    if not validate_csrf_token(token):
        return jsonify({"success": False, "error": "Token CSRF inválido o expirado."}), 400

    limite_raw = 50
    if request.is_json and request.json:
        limite_raw = request.json.get("limite", 50)
    elif request.form.get("limite"):
        limite_raw = request.form.get("limite")

    limite, _ = validar_limite_offset(limite_raw, 0, max_limite=200, default_limite=50)

    service = _get_service()
    resultado = service.procesar_cola(limite=limite)

    log_critical_action(
        accion="DESPACHO_COLA_NOTIFICACIONES",
        detalle=f"Despachadas {resultado.get('procesadas', 0)} notificaciones (Exito: {resultado.get('exitosas', 0)})",
    )

    return jsonify({"success": True, "resultado": resultado}), 200


@notification_bp.route("/recordatorios/evaluar", methods=["POST"])
@rol_requerido("Administrador", "Supervisor")
def evaluar_recordatorios():
    """Ejecuta el motor de reglas automáticas de 24 horas para generar recordatorios de corte."""
    token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not token and request.is_json and request.json:
        token = request.json.get("csrf_token")

    if not validate_csrf_token(token):
        return jsonify({"success": False, "error": "Token CSRF inválido o expirado."}), 400

    service = _get_service()
    ids_creados = service.evaluar_recordatorios_24h()

    log_critical_action(
        accion="EVALUAR_RECORDATORIOS_24H",
        detalle=f"Generadas {len(ids_creados)} alertas automáticas preventivas",
    )

    return jsonify({
        "success": True,
        "notificaciones_generadas": len(ids_creados),
        "ids": ids_creados,
    }), 200
