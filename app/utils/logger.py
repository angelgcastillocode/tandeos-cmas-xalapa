"""
Sistema de Logging y Auditoría Estructurada para la Plataforma CMAS Xalapa.
Permite el registro formal de eventos de autenticación, errores, cambios críticos,
importaciones masivas y operaciones operativas, omitiendo estrictamente cualquier credencial o token.
"""

import logging
import re
import sys
from typing import Any, Dict, Optional
from flask import Request, has_request_context, request, session

LOGGER_NAME = "cmas.audit"

# Expresiones regulares para censura preventiva de credenciales y secretos
PATRON_PASSWORD = re.compile(
    r"(?i)(password|contrasena|contraseña|credenciales|clave|secret|token|csrf_token)\s*[:=]\s*['\"]?([^'\"\s&,]+)",
)
PATRON_HASH = re.compile(
    r"(pbkdf2:sha256:\d+\$[a-zA-Z0-9/+=]+|\$2[abxy]\$\d+\$[a-zA-Z0-9./]+|scrypt:\d+:\d+:\d+\$[a-zA-Z0-9/+=]+)"
)


def mask_sensitive_data(mensaje: Any) -> str:
    """
    Sanitiza y enmascara preventivamente cualquier contraseña, secreto o hash
    criptográfico para garantizar que jamás se registre en texto plano.
    """
    if mensaje is None:
        return ""
    texto = str(mensaje)
    # Censurar campos con nombre de password/token
    texto = PATRON_PASSWORD.sub(r"\1=[REDACTED]", texto)
    # Censurar hashes completos
    texto = PATRON_HASH.sub(r"[HASH_REDACTED]", texto)
    return texto


class SensitiveDataFilter(logging.Filter):
    """Filtro de seguridad que intercepta y sanitiza los registros antes de emitirlos."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_sensitive_data(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    mask_sensitive_data(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: (mask_sensitive_data(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
        return True


class CMASAuditFormatter(logging.Formatter):
    """Formateador estructurado para eventos de auditoría institucional."""

    def format(self, record: logging.LogRecord) -> str:
        # Contexto de petición Flask si existe
        if has_request_context():
            record.ip = getattr(request, "remote_addr", "127.0.0.1") or "127.0.0.1"
            record.path = getattr(request, "path", "-")
            record.method = getattr(request, "method", "-")
            record.user_id = session.get("usuario_id", "anónimo")
            record.user_rol = session.get("usuario_rol", "-")
        else:
            record.ip = getattr(record, "ip", "-")
            record.path = getattr(record, "path", "-")
            record.method = getattr(record, "method", "-")
            record.user_id = getattr(record, "user_id", "sistema")
            record.user_rol = getattr(record, "user_rol", "-")

        return super().format(record)


def get_audit_logger() -> logging.Logger:
    """Devuelve el logger de auditoría de CMAS configurado con filtros de seguridad."""
    audit_logger = logging.getLogger(LOGGER_NAME)
    if not audit_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        fmt = (
            "[%(asctime)s] [%(levelname)s] [AUDIT] "
            "[IP: %(ip)s] [Usuario: %(user_id)s (%(user_rol)s)] "
            "[%(method)s %(path)s] %(message)s"
        )
        formatter = CMASAuditFormatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        audit_logger.addHandler(handler)
        audit_logger.setLevel(logging.INFO)
        audit_logger.propagate = False
    return audit_logger


def setup_logging(app) -> None:
    """Configura el sistema de logging para la aplicación Flask."""
    audit_logger = get_audit_logger()
    app.logger.handlers = audit_logger.handlers
    app.logger.setLevel(logging.INFO)


# =============================================================================
# Funciones Helper de Auditoría Segura (Sin exposición de credenciales)
# =============================================================================

def log_auth_success(correo: str, id_usuario: int, rol: str, ip: Optional[str] = None) -> None:
    """Registra un inicio de sesión exitoso sin registrar contraseñas."""
    logger = get_audit_logger()
    ip_str = ip or (request.remote_addr if has_request_context() else "127.0.0.1") or "127.0.0.1"
    logger.info(
        "AUTENTICACION_EXITOSA | Correo: %s | ID: %d | Rol: %s | Origen: %s",
        mask_sensitive_data(correo),
        id_usuario,
        rol,
        ip_str,
    )


def log_auth_failure(correo: str, motivo: str, ip: Optional[str] = None) -> None:
    """Registra un fallo de autenticación sin registrar la contraseña enviada."""
    logger = get_audit_logger()
    ip_str = ip or (request.remote_addr if has_request_context() else "127.0.0.1") or "127.0.0.1"
    logger.warning(
        "AUTENTICACION_FALLIDA | Correo: %s | Motivo: %s | Origen: %s",
        mask_sensitive_data(correo),
        mask_sensitive_data(motivo),
        ip_str,
    )


def log_critical_action(
    accion: str,
    detalle: str,
    usuario_id: Optional[int] = None,
    rol: Optional[str] = None,
) -> None:
    """Registra una acción administrativa u operativa de alto impacto."""
    logger = get_audit_logger()
    u_id = usuario_id or (session.get("usuario_id") if has_request_context() else "sistema")
    u_rol = rol or (session.get("usuario_rol") if has_request_context() else "-")
    logger.info(
        "ACCION_CRITICA | Accion: %s | Usuario: %s (%s) | Detalle: %s",
        mask_sensitive_data(accion),
        str(u_id),
        str(u_rol),
        mask_sensitive_data(detalle),
    )


def log_error_event(
    codigo: int,
    mensaje: str,
    path: Optional[str] = None,
    ip: Optional[str] = None,
    exception: Optional[Exception] = None,
) -> None:
    """Registra un error técnico del sistema omitiendo rutas privadas o trazas inseguras."""
    logger = get_audit_logger()
    req_path = path or (request.path if has_request_context() else "-")
    exc_type = type(exception).__name__ if exception else "None"
    logger.error(
        "ERROR_HTTP_%d | Ruta: %s | Excepcion: %s | Detalle: %s",
        codigo,
        req_path,
        exc_type,
        mask_sensitive_data(mensaje),
    )


def log_import_event(
    catalogo: str,
    registros_procesados: int,
    detalles: Optional[str] = None,
    usuario_id: Optional[int] = None,
) -> None:
    """Registra un evento de importación masiva de catálogos oficiales."""
    logger = get_audit_logger()
    u_id = usuario_id or (session.get("usuario_id") if has_request_context() else "sistema")
    logger.info(
        "IMPORTACION_CATALOGO | Catalogo: %s | Registros: %d | Usuario: %s | Detalle: %s",
        mask_sensitive_data(catalogo),
        registros_procesados,
        str(u_id),
        mask_sensitive_data(detalles or "Proceso completado"),
    )
