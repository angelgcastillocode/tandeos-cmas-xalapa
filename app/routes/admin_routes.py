"""
Rutas y Blueprint del Panel de Administración General de CMAS Tandeos.
Acceso restringido exclusivamente a usuarios con rol 'Administrador'.
"""

from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash, jsonify, abort,
)

from app.services.admin_service import AdminService
from app.utils.csrf import generate_csrf_token, validate_csrf_token
from app.utils.logger import log_critical_action
from app.utils.validators import (
    sanitizar_cadena,
    validar_entero_positivo,
    validar_estado_incidencia,
    validar_estado_servicio,
    validar_prioridad_aviso,
    validar_dia_semana,
    validar_hora,
    validar_texto_seguro,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view_func):
    """Decorador de seguridad: Exige sesión activa con rol Administrador."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("usuario_id"):
            if (
                request.is_json
                or request.path.startswith("/admin/api/")
                or "application/json" in (request.headers.get("Accept") or "")
            ):
                return jsonify({
                    "success": False,
                    "error": "Autenticación Requerida",
                    "mensaje": "Debe iniciar sesión como Administrador.",
                }), 401
            flash("Debe iniciar sesión como Administrador para acceder al panel.", "warning")
            return redirect(url_for("auth.login_form"))

        rol = session.get("usuario_rol")
        service = AdminService()
        if not service.validar_acceso_admin(rol):
            if (
                request.is_json
                or request.path.startswith("/admin/api/")
                or "application/json" in (request.headers.get("Accept") or "")
            ):
                return jsonify({
                    "success": False,
                    "error": "Acceso No Autorizado",
                    "mensaje": "Privilegios insuficientes.",
                }), 403
            abort(403)

        return view_func(*args, **kwargs)
    return wrapper


@admin_bp.route("/dashboard", methods=["GET"])
@admin_required
def dashboard():
    """Vista principal del Panel de Control de Administración CMAS."""
    service = AdminService()
    filtros = {
        "sector": sanitizar_cadena(request.args.get("sector")) or None,
        "colonia": sanitizar_cadena(request.args.get("colonia")) or None,
        "q": sanitizar_cadena(request.args.get("q")) or None,
        "estado_rep": sanitizar_cadena(request.args.get("estado_rep")) or None,
        "tipo_rep": sanitizar_cadena(request.args.get("tipo_rep")) or None,
    }

    datos = service.obtener_dashboard(filtros)
    csrf_token = generate_csrf_token()

    return render_template(
        "admin/dashboard.html",
        metricas=datos["metricas"],
        tandeos=datos["tandeos"],
        avisos=datos["avisos"],
        reportes=datos["reportes"],
        sectores=datos["sectores"],
        colonias=datos["colonias"],
        dias_semana=datos["dias_semana"],
        estados_servicio=datos["estados_servicio"],
        prioridades_aviso=datos["prioridades_aviso"],
        filtros=filtros,
        csrf_token=csrf_token,
        usuario_nombre=session.get("usuario_nombre"),
        usuario_rol=session.get("usuario_rol"),
    )


# ============================================================================
# ENDPOINTS DE GESTIÓN DE TANDEOS
# ============================================================================

@admin_bp.route("/tandeos/guardar", methods=["POST"])
@admin_required
def tandeos_guardar():
    """Crea o actualiza una regla de tandeo por colonia y día validando entradas estrictamente."""
    if not validate_csrf_token(request.form.get("csrf_token")):
        flash("Token CSRF inválido o sesión expirada.", "danger")
        return redirect(url_for("admin.dashboard"))

    # Validación de identificador de colonia
    es_val_col, id_colonia, err_col = validar_entero_positivo(request.form.get("id_colonia"), "id_colonia")
    if not es_val_col:
        flash(err_col or "Colonia inválida.", "danger")
        return redirect(url_for("admin.dashboard"))

    # Validación de día de la semana
    es_val_dia, dia_semana, err_dia = validar_dia_semana(request.form.get("dia_semana"))
    if not es_val_dia:
        flash(err_dia or "Día de la semana inválido.", "danger")
        return redirect(url_for("admin.dashboard"))

    # Validación de formato de horas (HH:MM)
    es_val_hini, hora_ini, err_hini = validar_hora(request.form.get("hora_inicio"))
    es_val_hfin, hora_fin, err_hfin = validar_hora(request.form.get("hora_fin"))
    if not es_val_hini or not es_val_hfin:
        flash(err_hini or err_hfin or "Horario inválido.", "danger")
        return redirect(url_for("admin.dashboard"))

    # Validación de estado de servicio
    es_val_est, estado_srv, err_est = validar_estado_servicio(request.form.get("estado_servicio"))
    if not es_val_est:
        flash(err_est or "Estado de servicio inválido.", "danger")
        return redirect(url_for("admin.dashboard"))

    service = AdminService()
    rol = session.get("usuario_rol", "")
    exito, mensaje = service.guardar_tandeo(request.form, rol)

    if exito:
        log_critical_action(
            accion="GUARDAR_TANDEO",
            detalle=f"Regla de tandeo guardada para colonia {id_colonia} día {dia_semana} ({hora_ini}-{hora_fin})",
            usuario_id=session.get("usuario_id"),
            rol=rol,
        )

    flash(mensaje, "success" if exito else "danger")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/tandeos/<int:id_programacion>/eliminar", methods=["POST"])
@admin_required
def tandeos_eliminar(id_programacion: int):
    """Elimina una regla de programación de tandeo."""
    if not validate_csrf_token(request.form.get("csrf_token")):
        flash("Token CSRF inválido o sesión expirada.", "danger")
        return redirect(url_for("admin.dashboard"))

    es_valido, id_prog_int, err = validar_entero_positivo(id_programacion, "id_programacion")
    if not es_valido or not id_prog_int:
        flash(err or "Identificador inválido.", "danger")
        return redirect(url_for("admin.dashboard"))

    service = AdminService()
    rol = session.get("usuario_rol", "")
    exito, mensaje = service.eliminar_tandeo(id_prog_int, rol)

    if exito:
        log_critical_action(
            accion="ELIMINAR_TANDEO",
            detalle=f"Regla de programación {id_prog_int} eliminada",
            usuario_id=session.get("usuario_id"),
            rol=rol,
        )

    flash(mensaje, "success" if exito else "danger")
    return redirect(url_for("admin.dashboard"))


# ============================================================================
# ENDPOINTS DE PUBLICACIÓN DE AVISOS INSTITUCIONALES
# ============================================================================

@admin_bp.route("/avisos/crear", methods=["POST"])
@admin_required
def avisos_crear():
    """Publica un aviso o alerta importante en el portal validando contenido y prioridad."""
    if not validate_csrf_token(request.form.get("csrf_token")):
        flash("Token CSRF inválido o sesión expirada.", "danger")
        return redirect(url_for("admin.dashboard"))

    # Validaciones de longitud y caracteres
    es_val_tit, titulo, err_tit = validar_texto_seguro(
        request.form.get("titulo"), "titulo", min_len=3, max_len=150
    )
    if not es_val_tit:
        flash(err_tit or "Título del aviso inválido.", "danger")
        return redirect(url_for("admin.dashboard"))

    es_val_msg, _, err_msg = validar_texto_seguro(
        request.form.get("mensaje"), "mensaje", min_len=5, max_len=1000
    )
    if not es_val_msg:
        flash(err_msg or "Contenido del aviso inválido.", "danger")
        return redirect(url_for("admin.dashboard"))

    es_val_prio, _, err_prio = validar_prioridad_aviso(request.form.get("prioridad"))
    if not es_val_prio:
        flash(err_prio or "Prioridad de aviso inválida.", "danger")
        return redirect(url_for("admin.dashboard"))

    service = AdminService()
    rol = session.get("usuario_rol", "")
    exito, mensaje = service.publicar_aviso(request.form, rol)

    if exito:
        log_critical_action(
            accion="CREAR_AVISO",
            detalle=f"Aviso institucional publicado: '{titulo[:40]}'",
            usuario_id=session.get("usuario_id"),
            rol=rol,
        )

    flash(mensaje, "success" if exito else "danger")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/avisos/<int:id_aviso>/alternar", methods=["POST"])
@admin_required
def avisos_alternar(id_aviso: int):
    """Activa o suspende un aviso institucional."""
    if not validate_csrf_token(request.form.get("csrf_token")):
        flash("Token CSRF inválido o sesión expirada.", "danger")
        return redirect(url_for("admin.dashboard"))

    es_valido, id_aviso_int, err = validar_entero_positivo(id_aviso, "id_aviso")
    if not es_valido or not id_aviso_int:
        flash(err or "Identificador inválido.", "danger")
        return redirect(url_for("admin.dashboard"))

    service = AdminService()
    rol = session.get("usuario_rol", "")
    exito, mensaje = service.alternar_estado_aviso(id_aviso_int, rol)

    if exito:
        log_critical_action(
            accion="ALTERNAR_ESTADO_AVISO",
            detalle=f"Estado del aviso {id_aviso_int} modificado",
            usuario_id=session.get("usuario_id"),
            rol=rol,
        )

    flash(mensaje, "success" if exito else "danger")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/avisos/<int:id_aviso>/eliminar", methods=["POST"])
@admin_required
def avisos_eliminar(id_aviso: int):
    """Elimina definitivamente un aviso."""
    if not validate_csrf_token(request.form.get("csrf_token")):
        flash("Token CSRF inválido o sesión expirada.", "danger")
        return redirect(url_for("admin.dashboard"))

    es_valido, id_aviso_int, err = validar_entero_positivo(id_aviso, "id_aviso")
    if not es_valido or not id_aviso_int:
        flash(err or "Identificador inválido.", "danger")
        return redirect(url_for("admin.dashboard"))

    service = AdminService()
    rol = session.get("usuario_rol", "")
    exito, mensaje = service.eliminar_aviso(id_aviso_int, rol)

    if exito:
        log_critical_action(
            accion="ELIMINAR_AVISO",
            detalle=f"Aviso {id_aviso_int} eliminado definitivamente",
            usuario_id=session.get("usuario_id"),
            rol=rol,
        )

    flash(mensaje, "success" if exito else "danger")
    return redirect(url_for("admin.dashboard"))


# ============================================================================
# ENDPOINTS DE MODERACIÓN DE REPORTES CIUDADANOS
# ============================================================================

@admin_bp.route("/reportes/<int:id_reporte>/moderar", methods=["POST"])
@admin_required
def reportes_moderar(id_reporte: int):
    """Modera el estado de un reporte ciudadano (Abierto, En proceso, Cerrado)."""
    if not validate_csrf_token(request.form.get("csrf_token")):
        flash("Token CSRF inválido o sesión expirada.", "danger")
        return redirect(url_for("admin.dashboard"))

    es_valido_id, id_rep_int, err_id = validar_entero_positivo(id_reporte, "id_reporte")
    if not es_valido_id or not id_rep_int:
        flash(err_id or "Identificador inválido.", "danger")
        return redirect(url_for("admin.dashboard"))

    raw_estado = (request.form.get("nuevo_estado") or "").strip()
    es_valido_est, nuevo_estado, err_est = validar_estado_incidencia(raw_estado)
    if not es_valido_est or not nuevo_estado:
        flash(err_est or "Estado de reporte inválido.", "danger")
        return redirect(url_for("admin.dashboard"))

    service = AdminService()
    rol = session.get("usuario_rol", "")
    exito, mensaje = service.moderar_reporte(id_rep_int, nuevo_estado, rol)

    if exito:
        log_critical_action(
            accion="MODERAR_REPORTE",
            detalle=f"Reporte {id_rep_int} cambiado a estado '{nuevo_estado}'",
            usuario_id=session.get("usuario_id"),
            rol=rol,
        )

    flash(mensaje, "success" if exito else "danger")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/api/metricas", methods=["GET"])
@admin_required
def api_metricas():
    """Endpoint REST con las métricas generales del sistema."""
    service = AdminService()
    datos = service.obtener_dashboard()
    return jsonify({"success": True, "metricas": datos["metricas"]})
