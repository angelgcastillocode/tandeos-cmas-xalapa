from flask import Blueprint, jsonify, render_template, request
from app.services.consulta_service import ConsultaService

public_bp = Blueprint("public", __name__)


def _consulta_service() -> ConsultaService:
    return ConsultaService()


@public_bp.route("/", methods=["GET"])
def index():
    """Página de inicio pública para consulta ciudadana de tandeos."""
    return render_template("public/index.html")


@public_bp.route("/api/consultar", methods=["GET"])
def consultar_api():
    """Endpoint REST público que devuelve el sector y calendario semanal para una colonia o CP."""
    termino = request.args.get("q", "")
    resultado = _consulta_service().consultar_por_termino(termino)
    status_code = 200 if resultado.get("success", False) else 400
    return jsonify(resultado), status_code
