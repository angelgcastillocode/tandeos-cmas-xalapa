from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from app.auth.decorators import login_required, require_login
from app.services.reporte_service import TIPOS_INCIDENCIA_VALIDOS, ReporteService
from app.utils.logger import log_critical_action
from app.utils.validators import (
    sanitizar_cadena,
    validar_entero_positivo,
    validar_folio,
)

reporte_bp = Blueprint("reportes", __name__)


def _get_service() -> ReporteService:
    return ReporteService()


@reporte_bp.route("/reportar", methods=["GET"])
@require_login
def form_reportar():
    """Pantalla P-03: Formulario para el levantamiento de un reporte ciudadano de incidencia."""
    service = _get_service()
    colonias = service.obtener_colonias_para_formulario()

    raw_colonia_id = request.args.get("colonia_id")
    colonia_id_preseleccionada = None
    if raw_colonia_id:
        es_val, val_id, _ = validar_entero_positivo(raw_colonia_id, "colonia_id")
        if es_val:
            colonia_id_preseleccionada = val_id

    datos = {}
    if session.get("usuario_nombre"):
        datos["nombre_ciudadano"] = session.get("usuario_nombre")

    return render_template(
        "public/reporte.html",
        colonias=colonias,
        colonia_id_seleccionada=colonia_id_preseleccionada,
        tipos_incidencia=TIPOS_INCIDENCIA_VALIDOS,
        datos=datos,
        error=None,
    ), 200


@reporte_bp.route("/reportar", methods=["POST"])
@require_login
def enviar_reporte():
    """Procesa el formulario de reporte ciudadano con validación y sanitización."""
    service = _get_service()
    id_usuario = session.get("usuario_id")

    nombre_ciudadano = sanitizar_cadena(request.form.get("nombre_ciudadano", ""))
    if not nombre_ciudadano and session.get("usuario_nombre"):
        nombre_ciudadano = session.get("usuario_nombre")

    datos = {
        "id_colonia": sanitizar_cadena(request.form.get("id_colonia", "")),
        "tipo_incidencia": sanitizar_cadena(request.form.get("tipo_incidencia", "")),
        "descripcion": sanitizar_cadena(request.form.get("descripcion", "")),
        "nombre_ciudadano": nombre_ciudadano,
        "telefono_contacto": sanitizar_cadena(request.form.get("telefono_contacto", "")),
        "id_usuario": id_usuario,
    }

    exito, folio, error_msg = service.registrar_reporte(datos)

    if not exito:
        colonias = service.obtener_colonias_para_formulario()
        try:
            col_id = int(datos["id_colonia"])
        except (ValueError, TypeError):
            col_id = None

        return (
            render_template(
                "public/reporte.html",
                colonias=colonias,
                colonia_id_seleccionada=col_id,
                tipos_incidencia=TIPOS_INCIDENCIA_VALIDOS,
                datos=datos,
                error=error_msg,
            ),
            400,
        )

    log_critical_action(
        accion="REGISTRO_REPORTE_CIUDADANO",
        detalle=f"Reporte ciudadano levantado exitosamente con folio {folio}",
        usuario_id=id_usuario,
        rol=session.get("usuario_rol"),
    )

    return redirect(url_for("reportes.reporte_exito", folio=folio))


@reporte_bp.route("/reporte/exito/<folio>", methods=["GET"])
def reporte_exito(folio: str):
    """Pantalla P-03 (Confirmación): Muestra el folio oficial generado y resumen del reporte."""
    es_val, folio_limpio, _ = validar_folio(folio)
    if not es_val or not folio_limpio:
        abort(404, description=f"No se encontró ningún reporte con el folio {folio}.")

    service = _get_service()
    reporte = service.obtener_reporte_por_folio(folio_limpio)

    if not reporte:
        abort(404, description=f"No se encontró ningún reporte con el folio {folio}.")

    return render_template(
        "public/reporte_exito.html",
        reporte=reporte,
    ), 200


@reporte_bp.route("/rastreador", methods=["GET"])
def rastreador():
    """Pantalla de Rastreador de Folio y Mis Reportes."""
    folio_raw = request.args.get("folio", "")
    service = _get_service()
    reporte = None
    folio_buscado = ""

    if folio_raw:
        es_val, folio_limpio, _ = validar_folio(folio_raw)
        if es_val and folio_limpio:
            folio_buscado = folio_limpio
            reporte = service.obtener_reporte_por_folio(folio_limpio)

    # Si hay usuario autenticado, obtener sus reportes
    mis_reportes = []
    id_usuario = session.get("usuario_id")
    if id_usuario:
        mis_reportes = service.obtener_reportes_por_usuario(id_usuario)

    return render_template(
        "public/rastreador.html",
        folio=folio_buscado,
        reporte=reporte,
        mis_reportes=mis_reportes,
        busqueda_realizada=bool(folio_raw),
    ), 200


@reporte_bp.route("/api/reportes/rastrear", methods=["GET"])
def api_rastrear_reporte():
    """Endpoint REST JSON para consulta asíncrona de folio de reporte."""
    folio_raw = request.args.get("folio", "")
    if not folio_raw:
        return {"success": False, "error": "Folio no proporcionado"}, 400

    es_val, folio_limpio, _ = validar_folio(folio_raw)
    if not es_val or not folio_limpio:
        return {"success": False, "error": "Formato de folio inválido"}, 400

    service = _get_service()
    reporte = service.obtener_reporte_por_folio(folio_limpio)
    if not reporte:
        return {"success": False, "error": "No se encontró ningún reporte con ese folio"}, 404

    return {"success": True, "reporte": reporte}, 200

