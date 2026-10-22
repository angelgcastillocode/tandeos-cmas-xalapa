"""
Blueprint y rutas del Panel de Supervisor y Técnico CMAS Xalapa.
Acceso protegido exclusivamente para roles operativos (Supervisor, Técnico).
"""

from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash, jsonify, abort,
)

from app.services.supervisor_service import SupervisorService
from app.utils.csrf import generate_csrf_token, validate_csrf_token
from app.utils.logger import log_critical_action
from app.utils.validators import (
    sanitizar_cadena,
    validar_entero_positivo,
    validar_estado_incidencia,
    validar_texto_seguro,
)

supervisor_bp = Blueprint("supervisor", __name__, url_prefix="/supervisor")


def supervisor_required(view_func):
    """Decorador de control de acceso: Restringe la vista a usuarios con rol operativo."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("usuario_id"):
            if (
                request.is_json
                or request.path.startswith("/supervisor/api/")
                or "application/json" in (request.headers.get("Accept") or "")
            ):
                return jsonify({
                    "success": False,
                    "error": "Autenticación Requerida",
                    "mensaje": "Debe iniciar sesión para acceder al panel de supervisión.",
                }), 401
            flash("Debe iniciar sesión para acceder al panel de supervisión.", "warning")
            return redirect(url_for("auth.login_form"))

        rol = session.get("usuario_rol")
        service = SupervisorService()
        if not service.validar_acceso_supervisor(rol):
            if (
                request.is_json
                or request.path.startswith("/supervisor/api/")
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


@supervisor_bp.route("/dashboard", methods=["GET"])
@supervisor_required
def dashboard():
    """Vista principal del Centro de Mando y Supervisión Operativa CMAS."""
    service = SupervisorService()
    filtros_raw = {
        "sector": sanitizar_cadena(request.args.get("sector")) or None,
        "colonia": sanitizar_cadena(request.args.get("colonia")) or None,
        "tipo": sanitizar_cadena(request.args.get("tipo")) or None,
        "estado": sanitizar_cadena(request.args.get("estado")) or None,
        "fecha_inicio": sanitizar_cadena(request.args.get("fecha_inicio")) or None,
        "fecha_fin": sanitizar_cadena(request.args.get("fecha_fin")) or None,
    }

    datos = service.obtener_dashboard(filtros_raw)
    csrf_token = generate_csrf_token()

    return render_template(
        "supervisor/dashboard.html",
        kpis=datos["kpis"],
        sectores_criticos=datos["sectores_criticos"],
        discrepancias=datos["discrepancias"],
        colonias_anomalias=datos["colonias_anomalias"],
        incidencias=datos["incidencias"],
        sectores_catalogo=datos["sectores_catalogo"],
        colonias_catalogo=datos["colonias_catalogo"],
        bitacora=datos["bitacora"],
        filtros=datos["filtros_aplicados"],
        csrf_token=csrf_token,
        usuario_nombre=session.get("usuario_nombre"),
        usuario_rol=session.get("usuario_rol"),
    )


@supervisor_bp.route("/api/metricas", methods=["GET"])
@supervisor_required
def api_metricas():
    """Endpoint REST que expone los indicadores y KPIs operativos consolidados."""
    service = SupervisorService()
    filtros_raw = {
        "sector": sanitizar_cadena(request.args.get("sector")) or None,
        "colonia": sanitizar_cadena(request.args.get("colonia")) or None,
        "tipo": sanitizar_cadena(request.args.get("tipo")) or None,
        "estado": sanitizar_cadena(request.args.get("estado")) or None,
        "fecha_inicio": sanitizar_cadena(request.args.get("fecha_inicio")) or None,
        "fecha_fin": sanitizar_cadena(request.args.get("fecha_fin")) or None,
    }
    datos = service.obtener_dashboard(filtros_raw)
    return jsonify({
        "success": True,
        "kpis": datos["kpis"],
        "sectores_criticos": datos["sectores_criticos"],
        "total_discrepancias": len(datos["discrepancias"]),
    })


@supervisor_bp.route("/api/discrepancias", methods=["GET"])
@supervisor_required
def api_discrepancias():
    """Endpoint REST con el cruce de anomalías entre tandeos activos y reportes de falta de agua."""
    service = SupervisorService()
    filtros_raw = {
        "sector": sanitizar_cadena(request.args.get("sector")) or None,
        "colonia": sanitizar_cadena(request.args.get("colonia")) or None,
        "fecha_inicio": sanitizar_cadena(request.args.get("fecha_inicio")) or None,
        "fecha_fin": sanitizar_cadena(request.args.get("fecha_fin")) or None,
    }
    datos = service.obtener_dashboard(filtros_raw)
    return jsonify({
        "success": True,
        "total": len(datos["discrepancias"]),
        "discrepancias": datos["discrepancias"],
    })


@supervisor_bp.route("/api/colonias", methods=["GET"])
@supervisor_required
def api_colonias_por_sector():
    """Endpoint auxiliar para poblar selectores dependientes de sector."""
    id_sector = request.args.get("id_sector")
    service = SupervisorService()
    sector_id_int = None
    if id_sector:
        es_val, s_int, _ = validar_entero_positivo(id_sector, "id_sector")
        if es_val:
            sector_id_int = s_int
    colonias = service._repo.listar_colonias_catalogo(sector_id_int)
    return jsonify({"success": True, "colonias": colonias})


@supervisor_bp.route("/reporte/<int:id_reporte>/estado", methods=["POST"])
@supervisor_required
def actualizar_estado(id_reporte: int):
    """Acción operativa para cambiar el estado de una incidencia (Abierto, En proceso, Cerrado)."""
    # 1. Validación estricta de CSRF
    token = request.form.get("csrf_token")
    if not validate_csrf_token(token):
        flash("La sesión ha expirado o el token CSRF es inválido. Intente nuevamente.", "danger")
        return redirect(url_for("supervisor.dashboard"))

    es_val_id, id_rep_int, err_id = validar_entero_positivo(id_reporte, "id_reporte")
    if not es_val_id or not id_rep_int:
        flash(err_id or "Identificador inválido.", "danger")
        return redirect(url_for("supervisor.dashboard"))

    raw_estado = (request.form.get("nuevo_estado") or "").strip()
    es_val_est, nuevo_estado, err_est = validar_estado_incidencia(raw_estado)
    if not es_val_est or not nuevo_estado:
        flash(err_est or "Estado de reporte inválido.", "danger")
        return redirect(url_for("supervisor.dashboard"))

    _, observaciones, _ = validar_texto_seguro(
        request.form.get("observaciones") or "",
        "observaciones",
        min_len=0,
        max_len=500,
    )

    id_usuario = session.get("usuario_id")
    rol_usuario = session.get("usuario_rol")

    service = SupervisorService()
    exito, mensaje = service.cambiar_estado_reporte(
        id_reporte=id_rep_int,
        nuevo_estado=nuevo_estado,
        id_usuario=id_usuario,
        rol_usuario=rol_usuario,
        observaciones=observaciones or "",
    )

    if exito:
        log_critical_action(
            accion="SUPERVISION_CAMBIO_ESTADO",
            detalle=f"Reporte {id_rep_int} actualizado a '{nuevo_estado}' por supervisor",
            usuario_id=id_usuario,
            rol=rol_usuario,
        )
        flash(mensaje, "success")
    else:
        flash(mensaje, "danger")

    return redirect(url_for("supervisor.dashboard"))
