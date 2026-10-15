from flask import Blueprint, jsonify, render_template, request
from app.services.consulta_service import ConsultaService
from app.utils.validators import sanitizar_cadena

consulta_bp = Blueprint("consulta", __name__)


def _get_service() -> ConsultaService:
    return ConsultaService()


@consulta_bp.route("/consulta", methods=["GET"])
def vista_calendario():
    """Vista web completa para la consulta y calendario semanal de tandeos (CU-001)."""
    termino = sanitizar_cadena(request.args.get("q", ""))

    sugerencias_default = [
        {"nombre": "Centro", "cp": "91000"},
        {"nombre": "Las Ánimas", "cp": "91190"},
        {"nombre": "Coapexpan", "cp": "91070"},
        {"nombre": "C.P. 91000", "cp": "91000"},
        {"nombre": "C.P. 91070", "cp": "91070"},
    ]

    # Si no se pasó término, mostrar página con buscador inicial
    if not termino:
        return render_template(
            "public/calendario.html",
            resultado=None,
            q="",
            sugerencias=sugerencias_default,
        ), 200

    # Límite preventivo de longitud para evitar ataques DoS por expresiones regulares o payloads gigantes
    if len(termino) > 100:
        termino = termino[:100]

    service = _get_service()
    resultado = service.consultar_por_termino(termino)

    # Si la validación de negocio falló (ej. menos de 2 chars o CP que no tiene 5 dígitos)
    if not resultado.get("success", False):
        return render_template(
            "public/calendario.html",
            resultado=resultado,
            q=termino,
            sugerencias=sugerencias_default,
        ), 400

    # Retorno 200 OK tanto si se encontró como si no hubo coincidencias
    return render_template(
        "public/calendario.html",
        resultado=resultado,
        q=termino,
        colonia=resultado.get("colonia"),
        sector=resultado.get("sector"),
        programacion=resultado.get("programacion", []),
        coincidencias=resultado.get("coincidencias", []),
        fiabilidad=resultado.get("fiabilidad"),
        ultima_actualizacion=resultado.get("ultima_actualizacion"),
        sugerencias=sugerencias_default,
    ), 200


@consulta_bp.route("/api/v1/tandeos/buscar", methods=["GET"])
def api_buscar_tandeos():
    """API REST pública para consulta asíncrona de tandeos.
    Devuelve respuesta JSON estructurada con la información de la colonia,
    sector asignado, programación semanal cronológica y métrica de fiabilidad.
    """
    termino = sanitizar_cadena(request.args.get("q", ""))
    if len(termino) > 100:
        termino = termino[:100]

    service = _get_service()
    resultado = service.consultar_por_termino(termino)

    status_code = 200 if resultado.get("success", False) else 400
    return jsonify(resultado), status_code
