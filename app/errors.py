"""
Manejo Centralizado de Errores Corporativos de la Plataforma CMAS Xalapa.
Captura códigos HTTP 400, 401, 403, 404, 409, 422 y 500, bloqueando por completo
la exposición de stack traces y registrando detalles técnicos en el sistema de auditoría.
"""

from typing import Any, Dict, Optional, Tuple
from flask import Flask, jsonify, render_template_string, request, session
from werkzeug.exceptions import HTTPException

from app.utils.logger import log_error_event

ERROR_TITULOS: Dict[int, str] = {
    400: "Solicitud Incorrecta",
    401: "Autenticación Requerida",
    403: "Acceso No Autorizado",
    404: "Recurso No Encontrado",
    409: "Conflicto con el Recurso",
    422: "Datos No Procesables",
    500: "Error Interno del Servidor",
}

ERROR_MENSAJES: Dict[int, str] = {
    400: "Los parámetros enviados en la solicitud no cumplen con el formato o las reglas de validación.",
    401: "Debe autenticarse con credenciales válidas para acceder a este recurso.",
    403: "No cuenta con los privilegios o permisos necesarios para realizar esta acción.",
    404: "El recurso, página o registro solicitado no existe o ha sido reubicado.",
    409: "La operación no se pudo completar debido a un conflicto con el estado actual del recurso.",
    422: "La solicitud contiene errores semánticos en los datos proporcionados.",
    500: "Se ha producido una eventualidad técnica en el servidor. El incidente ha sido registrado.",
}

# Plantilla HTML institucional limpia y segura sin tracebacks ni rutas privadas del sistema
HTML_ERROR_TEMPLATE = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ codigo }} - {{ titulo }} | CMAS Xalapa</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
  <style>
    body { background-color: #f4f7f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .card-error { max-width: 540px; border: none; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
    .badge-code { font-size: 1.1rem; padding: 0.4rem 0.8rem; border-radius: 6px; }
  </style>
</head>
<body class="d-flex align-items-center justify-content-center min-vh-100 p-3">
  <div class="card card-error text-center p-4 p-md-5 bg-white">
    <div class="mb-3">
      {% if codigo >= 500 %}
        <i class="bi bi-gear-wide-connected text-danger" style="font-size: 3.5rem;"></i>
      {% elif codigo == 403 or codigo == 401 %}
        <i class="bi bi-shield-lock-fill text-warning" style="font-size: 3.5rem;"></i>
      {% else %}
        <i class="bi bi-exclamation-circle-fill text-secondary" style="font-size: 3.5rem;"></i>
      {% endif %}
    </div>
    <span class="badge bg-light text-dark badge-code align-self-center mb-3">HTTP {{ codigo }}</span>
    <h2 class="h4 fw-bold text-dark mb-2">{{ titulo }}</h2>
    <p class="text-muted mb-4">{{ mensaje }}</p>
    <div class="d-flex justify-content-center gap-2">
      <a href="/" class="btn btn-primary fw-semibold px-4">Ir al Inicio</a>
      <a href="javascript:history.back()" class="btn btn-outline-secondary px-3">Regresar</a>
    </div>
  </div>
</body>
</html>
"""


def _es_peticion_json() -> bool:
    """Determina si la petición actual espera una respuesta JSON."""
    if request.is_json:
        return True
    if "/api/" in request.path or request.path.endswith(".json"):
        return True
    accept = request.headers.get("Accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return True
    if accept == "application/json":
        return True
    return False


def _filtrar_mensaje_seguro(codigo: int, mensaje: Optional[str]) -> str:
    """Garantiza que ningún mensaje contenga rutas del servidor, excepciones o fragmentos de stack trace."""
    if not mensaje:
        return ERROR_MENSAJES.get(codigo, "Ha ocurrido un error en la solicitud.")
    texto = str(mensaje)
    palabras_sospechosas = (
        "Traceback",
        "File \"",
        " line ",
        "sqlite3.",
        "OperationalError",
        "ProgrammingError",
        "DatabaseError",
        "ZeroDivisionError",
        "KeyError",
        "TypeError",
        "AttributeError",
        "SyntaxError",
    )
    if any(p in texto for p in palabras_sospechosas):
        return ERROR_MENSAJES.get(codigo, "Ha ocurrido un error en la solicitud.")
    return texto


def _construir_respuesta_error(codigo: int, descripcion_adicional: Optional[str] = None) -> Tuple[Any, int]:
    """Genera la respuesta apropiada (JSON o HTML) garantizando no filtrar trazas técnicas."""
    titulo = ERROR_TITULOS.get(codigo, "Error HTTP")
    # Para 500 nunca usar la descripción de excepción
    if codigo >= 500:
        mensaje = ERROR_MENSAJES.get(500, "Error interno del servidor.")
    else:
        mensaje = _filtrar_mensaje_seguro(codigo, descripcion_adicional or ERROR_MENSAJES.get(codigo))

    # Si es cliente API o petición JSON
    if _es_peticion_json():
        return (
            jsonify({
                "success": False,
                "error": titulo,
                "codigo": codigo,
                "mensaje": mensaje,
                "ruta": request.path,
            }),
            codigo,
        )

    # Si es navegador web estándar
    return (
        render_template_string(
            HTML_ERROR_TEMPLATE,
            codigo=codigo,
            titulo=titulo,
            mensaje=mensaje,
        ),
        codigo,
    )


def register_error_handlers(app: Flask) -> None:
    """Registra los manejadores globales para Flask asegurando auditoría y sanitización de salida."""

    def crear_handler(codigo: int):
        def handler(err):
            desc = None
            if isinstance(err, HTTPException) and err.description:
                desc = err.description
            log_error_event(
                codigo=codigo,
                mensaje=str(desc or ERROR_MENSAJES.get(codigo, "Error HTTP")),
                exception=err if isinstance(err, Exception) else None,
            )
            return _construir_respuesta_error(codigo, desc)
        return handler

    # Registrar para cada código requerido: 400, 401, 403, 404, 409, 422
    for cod in [400, 401, 403, 404, 409, 422]:
        app.register_error_handler(cod, crear_handler(cod))

    # Manejador global para 500 y excepciones no controladas
    @app.errorhandler(500)
    @app.errorhandler(Exception)
    def handle_500_internal_error(err):
        if isinstance(err, HTTPException):
            code = err.code or 500
            desc = err.description if code < 500 else None
            log_error_event(
                codigo=code,
                mensaje=str(desc or ERROR_MENSAJES.get(code, "Error")),
                exception=err,
            )
            return _construir_respuesta_error(code, desc)

        # Excepciones técnicas del servidor (RuntimeError, ZeroDivisionError, sqlite3, etc.)
        log_error_event(
            codigo=500,
            mensaje="Excepción interna no controlada",
            exception=err,
        )
        return _construir_respuesta_error(500)
