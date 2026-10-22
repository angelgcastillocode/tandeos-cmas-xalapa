from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ReporteCiudadano:
    """Representación de un reporte o incidencia ciudadana de agua en CMAS Xalapa."""
    folio: str
    id_colonia: int
    tipo_incidencia: str
    descripcion: str
    id_reporte: Optional[int] = None
    id_usuario: Optional[int] = None
    nombre_ciudadano: Optional[str] = None
    telefono_contacto: Optional[str] = None
    fecha_hora_reporte: Optional[str] = None
    estado: str = "Abierto"
    nombre_colonia: Optional[str] = None
    codigo_postal: Optional[str] = None
