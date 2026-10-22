import html
import random
import re
import string
from typing import Any, Dict, List, Optional, Tuple
from app.models.reporte import ReporteCiudadano
from app.repositories.reporte_repository import ReporteRepository

TIPOS_INCIDENCIA_VALIDOS = (
    "Falta de agua",
    "Fuga",
    "Baja presión",
    "Mantenimiento",
    "Otro",
)


class ReporteService:
    """Lógica de negocio para la validación, generación de folios y registro de reportes ciudadanos."""

    def __init__(self, repo: Optional[ReporteRepository] = None) -> None:
        self._repo = repo or ReporteRepository()

    def generar_folio_unico(self, anio: int = 2026) -> str:
        """Genera un folio único en formato RPT-2026-XXXXX con 5 caracteres alfanuméricos en mayúsculas.
        Garantiza la ausencia de colisiones verificando contra la base de datos.
        """
        caracteres = string.ascii_uppercase + string.digits
        # Intentar hasta encontrar un folio no repetido
        for _ in range(100):
            sufijo = "".join(random.choices(caracteres, k=5))
            folio_candidato = f"RPT-{anio}-{sufijo}"
            if not self._repo.existe_folio(folio_candidato):
                return folio_candidato

        raise RuntimeError("No se pudo generar un folio único tras múltiples intentos.")

    def sanitizar_texto(self, texto: Optional[str]) -> str:
        """Sanitiza el texto eliminando etiquetas peligrosas y aplicando escape contra XSS."""
        if not texto:
            return ""
        # Limpiar tags HTML básicos
        limpio = re.sub(r"<[^>]*>", "", texto.strip())
        return html.escape(limpio)

    def validar_datos_reporte(self, datos: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Valida las reglas de negocio de un reporte ciudadano:
        - id_colonia existente en BD.
        - tipo_incidencia válido.
        - descripcion obligatoria (mínimo 15 caracteres).
        - telefono opcional (entre 10 y 15 dígitos si se suministra).
        """
        # 1. Validación de id_colonia
        raw_colonia = datos.get("id_colonia")
        try:
            id_colonia = int(raw_colonia)
        except (ValueError, TypeError):
            return False, "Debe seleccionar una colonia válida de la lista."

        if not self._repo.colonia_existe(id_colonia):
            return False, "La colonia seleccionada no existe en el registro municipal."

        # 2. Validación de tipo_incidencia
        tipo = (datos.get("tipo_incidencia") or "").strip()
        if tipo not in TIPOS_INCIDENCIA_VALIDOS:
            return (
                False,
                f"El tipo de incidencia debe ser uno de los siguientes: {', '.join(TIPOS_INCIDENCIA_VALIDOS)}.",
            )

        # 3. Validación de descripción
        descripcion = (datos.get("descripcion") or "").strip()
        if len(descripcion) < 15:
            return (
                False,
                "La descripción de la anomalía es obligatoria y debe tener al menos 15 caracteres.",
            )

        # 4. Validación de teléfono de contacto (si se proporciona)
        telefono = (datos.get("telefono_contacto") or "").strip()
        if telefono:
            digitos_tel = re.sub(r"\D", "", telefono)
            if len(digitos_tel) < 10 or len(digitos_tel) > 15:
                return False, "El teléfono de contacto debe contener entre 10 y 15 dígitos numéricos."

        return True, None

    def registrar_reporte(self, datos: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str]]:
        """Valida, sanitiza, genera folio e inserta un nuevo reporte ciudadano.
        Retorna (exito, folio, mensaje_error).
        """
        es_valido, error = self.validar_datos_reporte(datos)
        if not es_valido:
            return False, None, error

        id_colonia = int(datos["id_colonia"])
        tipo = datos["tipo_incidencia"].strip()
        descripcion_limpia = self.sanitizar_texto(datos.get("descripcion"))
        nombre_limpio = self.sanitizar_texto(datos.get("nombre_ciudadano")) or None
        telefono_limpio = (datos.get("telefono_contacto") or "").strip() or None

        raw_id_usuario = datos.get("id_usuario")
        id_usuario = None
        if raw_id_usuario is not None:
            try:
                id_usuario = int(raw_id_usuario)
            except (ValueError, TypeError):
                id_usuario = None

        folio = self.generar_folio_unico()

        reporte = ReporteCiudadano(
            folio=folio,
            id_colonia=id_colonia,
            tipo_incidencia=tipo,
            descripcion=descripcion_limpia,
            nombre_ciudadano=nombre_limpio,
            telefono_contacto=telefono_limpio,
            id_usuario=id_usuario,
            estado="Abierto",
        )

        try:
            self._repo.crear_reporte(reporte)
            return True, folio, None
        except Exception as e:
            return False, None, f"Error al guardar el reporte: {str(e)}"

    def obtener_reporte_por_folio(self, folio: str) -> Optional[Dict[str, Any]]:
        """Recupera el reporte ciudadano por su folio asignado."""
        if not folio:
            return None
        return self._repo.obtener_por_folio(folio)

    def obtener_colonias_para_formulario(self) -> List[Dict[str, Any]]:
        """Obtiene el catálogo de colonias registradas para poblar el <select> del formulario."""
        return self._repo.listar_colonias()
