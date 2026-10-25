"""
Módulo de Validación Estricta y Sanitización de Entradas (Backend Hardening).
Protege contra ataques de inyección, manipulación de parámetros, IDOR y caracteres de control.
"""

import re
from datetime import datetime
from typing import Any, Optional, Set, Tuple

RE_CORREO = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
RE_TELEFONO = re.compile(r"^\d{10}$")
RE_CP = re.compile(r"^\d{5}$")
RE_HORA = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
RE_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_FOLIO = re.compile(r"^RPT-\d{4}-[A-Z0-9]{4,10}$", re.IGNORECASE)

DIAS_VALIDOS: Set[str] = {
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
}

ESTADOS_INCIDENCIA_VALIDOS: Set[str] = {"Abierto", "En proceso", "Cerrado"}

TIPOS_INCIDENCIA_VALIDOS: Set[str] = {
    "Falta de agua",
    "Fuga",
    "Baja presión",
    "Mantenimiento",
    "Otro",
}

ESTADOS_SERVICIO_VALIDOS: Set[str] = {"Activo", "Suspendido", "Mantenimiento"}

PRIORIDADES_AVISO_VALIDAS: Set[str] = {"Normal", "Alta", "Urgente"}

CANALES_NOTIFICACION_VALIDOS: Set[str] = {"email", "sms"}

TIPOS_NOTIFICACION_VALIDOS: Set[str] = {
    "recordatorio_corte",
    "inicio_tandeo",
    "cambio_programacion",
    "suspension",
    "mantenimiento",
    "contingencia",
    "confirmacion_reporte",
}


def sanitizar_cadena(valor: Any) -> str:
    """Elimina bytes nulos y caracteres de control invisibles que puedan alterar consultas o flujos."""
    if valor is None:
        return ""
    texto = str(valor)
    # Eliminar bytes nulos y retornos de carro peligrosos
    texto = texto.replace("\x00", "").replace("\r", "")
    return texto.strip()


def contiene_caracteres_peligrosos(valor: Any) -> bool:
    """Detecta si la entrada contiene bytes nulos u otros caracteres no imprimibles maliciosos."""
    if valor is None:
        return False
    texto = str(valor)
    return "\x00" in texto or any(ord(c) < 32 and c not in "\t\n\r" for c in texto)


def sanitizar_sql_like(patron: str) -> str:
    """Escapa comodines % y _ para búsquedas seguras con LIKE parametrizado."""
    texto = sanitizar_cadena(patron)
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def validar_entero_positivo(
    valor: Any,
    nombre_campo: str = "id",
    minimo: int = 1,
    maximo: int = 2147483647,
) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Valida y convierte un identificador numérico entero en un rango seguro.
    Previene desbordamientos de enteros, inyecciones de caracteres y números negativos.
    """
    if valor is None:
        return False, None, f"El campo '{nombre_campo}' es obligatorio."
    try:
        texto = sanitizar_cadena(valor)
        if not texto:
            return False, None, f"El campo '{nombre_campo}' no puede estar vacío."
        val_int = int(texto)
    except (ValueError, TypeError):
        return False, None, f"El campo '{nombre_campo}' debe ser un número entero válido."

    if val_int < minimo or val_int > maximo:
        return False, None, f"El campo '{nombre_campo}' debe estar entre {minimo} y {maximo}."

    return True, val_int, None


def validar_texto_seguro(
    valor: Any,
    nombre_campo: str,
    min_len: int = 1,
    max_len: int = 255,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Valida longitud y contenido de texto libre evitando desbordamientos de búfer.
    """
    texto = sanitizar_cadena(valor)
    if len(texto) < min_len:
        return False, None, f"El campo '{nombre_campo}' debe contener al menos {min_len} caracteres."
    if len(texto) > max_len:
        return False, None, f"El campo '{nombre_campo}' no debe exceder {max_len} caracteres."
    return True, texto, None


def validar_correo(correo: Any) -> Tuple[bool, Optional[str], Optional[str]]:
    """Valida formato estricto y longitud de un correo electrónico."""
    texto = sanitizar_cadena(correo).lower()
    if not texto:
        return False, None, "El correo electrónico es obligatorio."
    if len(texto) > 120:
        return False, None, "El correo electrónico no debe exceder 120 caracteres."
    if not RE_CORREO.match(texto):
        return False, None, "El formato del correo electrónico es inválido."
    return True, texto, None


def validar_telefono(telefono: Any, opcional: bool = True) -> Tuple[bool, Optional[str], Optional[str]]:
    """Valida número telefónico a 10 dígitos numéricos."""
    texto = sanitizar_cadena(telefono)
    if not texto:
        if opcional:
            return True, None, None
        return False, None, "El teléfono de contacto es obligatorio."

    # Limpiar posibles guiones o espacios
    numeros = "".join(ch for ch in texto if ch.isdigit())
    if not RE_TELEFONO.match(numeros):
        return False, None, "El teléfono debe contener exactamente 10 dígitos numéricos."
    return True, numeros, None


def validar_codigo_postal(cp: Any) -> Tuple[bool, Optional[str], Optional[str]]:
    """Valida código postal mexicano a 5 dígitos numéricos."""
    texto = sanitizar_cadena(cp)
    if not RE_CP.match(texto):
        return False, None, "El código postal debe constar de exactamente 5 dígitos numéricos."
    return True, texto, None


def validar_estado_incidencia(estado: Any) -> Tuple[bool, Optional[str], Optional[str]]:
    """Valida que el estado de reporte pertenezca al catálogo permitido."""
    texto = sanitizar_cadena(estado)
    if texto not in ESTADOS_INCIDENCIA_VALIDOS:
        return (
            False,
            None,
            f"Estado inválido: '{texto}'. Debe ser uno de: {', '.join(sorted(ESTADOS_INCIDENCIA_VALIDOS))}.",
        )
    return True, texto, None


def validar_tipo_incidencia(tipo: Any) -> Tuple[bool, Optional[str], Optional[str]]:
    """Valida que el tipo de incidencia pertenezca al catálogo oficial."""
    texto = sanitizar_cadena(tipo)
    if texto not in TIPOS_INCIDENCIA_VALIDOS:
        return (
            False,
            None,
            f"Tipo de incidencia inválido: '{texto}'. Debe ser uno de: {', '.join(sorted(TIPOS_INCIDENCIA_VALIDOS))}.",
        )
    return True, texto, None


def validar_dia_semana(dia: Any) -> Tuple[bool, Optional[str], Optional[str]]:
    """Valida día de la semana con mayúscula inicial y tildes oficiales."""
    texto = sanitizar_cadena(dia)
    if texto not in DIAS_VALIDOS:
        return False, None, f"Día de la semana inválido: '{texto}'."
    return True, texto, None


def validar_hora(hora_str: Any) -> Tuple[bool, Optional[str], Optional[str]]:
    """Valida formato de hora en reloj de 24 horas (HH:MM)."""
    texto = sanitizar_cadena(hora_str)
    if not RE_HORA.match(texto):
        return False, None, f"Formato de hora inválido: '{texto}'. Debe cumplir el formato HH:MM (00:00 a 23:59)."
    return True, texto, None


def validar_fecha(fecha_str: Any, nombre_campo: str = "fecha") -> Tuple[bool, Optional[str], Optional[str]]:
    """Valida formato de fecha calendario en formato ISO YYYY-MM-DD."""
    texto = sanitizar_cadena(fecha_str)
    if not RE_FECHA.match(texto):
        return False, None, f"Formato de '{nombre_campo}' inválido: '{texto}'. Se requiere YYYY-MM-DD."
    try:
        datetime.strptime(texto, "%Y-%m-%d")
    except ValueError:
        return False, None, f"La fecha '{texto}' no corresponde a una fecha válida del calendario."
    return True, texto, None


def validar_folio(folio: Any) -> Tuple[bool, Optional[str], Optional[str]]:
    """Valida el formato de folio oficial de reporte (ej. RPT-2026-ABC12)."""
    texto = sanitizar_cadena(folio).upper()
    if not RE_FOLIO.match(texto):
        return False, None, f"Formato de folio inválido: '{texto}'."
    return True, texto, None


def validar_estado_servicio(estado: Any) -> Tuple[bool, Optional[str], Optional[str]]:
    """Valida que el estado del servicio de tandeo sea Activo, Suspendido o Mantenimiento."""
    texto = sanitizar_cadena(estado)
    if texto not in ESTADOS_SERVICIO_VALIDOS:
        return (
            False,
            None,
            f"Estado de servicio inválido: '{texto}'. Debe ser uno de: {', '.join(sorted(ESTADOS_SERVICIO_VALIDOS))}.",
        )
    return True, texto, None


def validar_prioridad_aviso(prioridad: Any) -> Tuple[bool, Optional[str], Optional[str]]:
    """Valida que la prioridad de aviso sea Normal, Alta o Urgente."""
    texto = sanitizar_cadena(prioridad)
    if texto not in PRIORIDADES_AVISO_VALIDAS:
        return (
            False,
            None,
            f"Prioridad inválida: '{texto}'. Debe ser una de: {', '.join(sorted(PRIORIDADES_AVISO_VALIDAS))}.",
        )
    return True, texto, None


def validar_canal_notificacion(canal: Any) -> Tuple[bool, Optional[str], Optional[str]]:
    """Valida canal de despacho de notificaciones (email o sms)."""
    texto = sanitizar_cadena(canal).lower()
    if texto not in CANALES_NOTIFICACION_VALIDOS:
        return (
            False,
            None,
            f"Canal inválido: '{texto}'. Debe ser 'email' o 'sms'.",
        )
    return True, texto, None


def validar_tipo_notificacion(tipo: Any) -> Tuple[bool, Optional[str], Optional[str]]:
    """Valida que el tipo de evento de notificación sea uno de los soportados por CMAS."""
    texto = sanitizar_cadena(tipo)
    if texto not in TIPOS_NOTIFICACION_VALIDOS:
        return (
            False,
            None,
            f"Tipo de notificación inválido: '{texto}'. Debe ser uno de: {', '.join(sorted(TIPOS_NOTIFICACION_VALIDOS))}.",
        )
    return True, texto, None


def validar_limite_offset(
    limite: Any,
    offset: Any,
    max_limite: int = 100,
    default_limite: int = 50,
) -> Tuple[int, int]:
    """Valida y acota numéricamente los parámetros de paginación contra desbordamientos y valores negativos."""
    try:
        lim = int(limite)
    except (ValueError, TypeError):
        lim = default_limite

    try:
        off = int(offset)
    except (ValueError, TypeError):
        off = 0

    lim = max(1, min(lim, max_limite))
    off = max(0, off)
    return lim, off


# =============================================================================
# Control de Autorización y Prevención de IDOR (Insecure Direct Object Reference)
# =============================================================================

def validar_permiso_acceso(
    usuario_id_sesion: Optional[int],
    rol_sesion: Optional[str],
    recurso_usuario_id: int,
) -> bool:
    """
    Verifica que el usuario actual tenga autorización para acceder o modificar el recurso.
    - Los administradores y supervisores tienen acceso global.
    - Los usuarios estándar únicamente pueden acceder a recursos que les pertenezcan (mismo id).
    """
    if not usuario_id_sesion:
        return False
    if rol_sesion in ("Administrador", "Supervisor"):
        return True
    try:
        return int(usuario_id_sesion) == int(recurso_usuario_id)
    except (ValueError, TypeError):
        return False
