"""
Servicio de negocio para el Panel de Administración General de CMAS.
Encapsula las reglas para la gestión de calendarios, publicación de alertas
y moderación de incidencias ciudadanas, verificando privilegios administrativos.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from app.repositories.admin_repository import AdminRepository

DIAS_VALIDOS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
ESTADOS_SERVICIO_VALIDOS = ("Activo", "Suspendido", "Mantenimiento")
PRIORIDADES_AVISO = ("Baja", "Normal", "Alta", "Urgente")
ESTADOS_REPORTE_VALIDOS = ("Abierto", "En proceso", "Cerrado")
HORA_REGEX = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class AdminService:
    """Lógica de administración general y gestión de catálogos y avisos."""

    def __init__(self, repository: Optional[AdminRepository] = None):
        self._repo = repository or AdminRepository()

    def validar_acceso_admin(self, rol: Optional[str]) -> bool:
        """Verifica que el usuario cuente estrictamente con privilegios de Administrador."""
        return rol == "Administrador"

    def obtener_dashboard(self, filtros: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Recopila todas las métricas, programaciones, avisos y reportes para el panel de administración."""
        filtros = filtros or {}

        metricas = self._repo.obtener_metricas_generales()
        tandeos = self._repo.listar_programaciones(
            id_sector=filtros.get("sector"),
            id_colonia=filtros.get("colonia"),
            termino=filtros.get("q"),
            limite=60,
        )
        avisos = self._repo.listar_avisos(limite=20)
        reportes = self._repo.listar_reportes_moderacion(
            estado=filtros.get("estado_rep"),
            tipo=filtros.get("tipo_rep"),
            limite=30,
        )
        sectores = self._repo.listar_sectores()
        colonias = self._repo.listar_colonias(filtros.get("sector"))

        return {
            "metricas": metricas,
            "tandeos": tandeos,
            "avisos": avisos,
            "reportes": reportes,
            "sectores": sectores,
            "colonias": colonias,
            "dias_semana": DIAS_VALIDOS,
            "estados_servicio": ESTADOS_SERVICIO_VALIDOS,
            "prioridades_aviso": PRIORIDADES_AVISO,
            "filtros": filtros,
        }

    # ========================================================================
    # GESTIÓN DE CALENDARIOS Y TANDEOS
    # ========================================================================

    def guardar_tandeo(self, datos: Dict[str, Any], rol_usuario: str) -> Tuple[bool, str]:
        """Valida y guarda una regla de programación de tandeo por colonia."""
        if not self.validar_acceso_admin(rol_usuario):
            return False, "Acción denegada: Se requieren privilegios de Administrador General."

        try:
            id_colonia = int(datos.get("id_colonia", 0))
        except (ValueError, TypeError):
            return False, "Debe seleccionar una colonia válida."

        if id_colonia <= 0:
            return False, "Debe seleccionar una colonia válida."

        dia = (datos.get("dia_semana") or "").strip()
        if dia not in DIAS_VALIDOS:
            return False, f"Día de la semana inválido. Debe ser uno de: {', '.join(DIAS_VALIDOS)}"

        h_ini = (datos.get("hora_inicio") or "").strip()
        h_fin = (datos.get("hora_fin") or "").strip()

        if not HORA_REGEX.match(h_ini) or not HORA_REGEX.match(h_fin):
            return False, "El formato de horario debe ser HH:MM (24 horas, ej. 08:00)."

        if h_ini >= h_fin:
            return False, "La hora de inicio debe ser anterior a la hora de fin."

        estado = (datos.get("estado_servicio") or "").strip()
        if estado not in ESTADOS_SERVICIO_VALIDOS:
            return False, f"Estado de servicio inválido. Opciones: {', '.join(ESTADOS_SERVICIO_VALIDOS)}"

        return self._repo.guardar_programacion_tandeo(
            id_colonia=id_colonia,
            dia_semana=dia,
            hora_inicio=h_ini,
            hora_fin=h_fin,
            estado_servicio=estado,
        )

    def eliminar_tandeo(self, id_programacion: int, rol_usuario: str) -> Tuple[bool, str]:
        """Elimina una regla de programación de tandeo existente."""
        if not self.validar_acceso_admin(rol_usuario):
            return False, "Acción denegada: Se requieren privilegios de Administrador General."

        exito = self._repo.eliminar_programacion_tandeo(id_programacion)
        if exito:
            return True, f"Programación #{id_programacion} eliminada correctamente."
        return False, "No se encontró la programación especificada."

    # ========================================================================
    # GESTIÓN DE AVISOS Y ALERTAS INSTITUCIONALES
    # ========================================================================

    def publicar_aviso(self, datos: Dict[str, Any], rol_usuario: str) -> Tuple[bool, str]:
        """Valida y publica un aviso oficial de CMAS."""
        if not self.validar_acceso_admin(rol_usuario):
            return False, "Acción denegada: Se requieren privilegios de Administrador General."

        titulo = (datos.get("titulo") or "").strip()
        if len(titulo) < 5:
            return False, "El título del aviso debe tener al menos 5 caracteres."

        contenido = (datos.get("contenido") or "").strip()
        if len(contenido) < 10:
            return False, "El contenido del aviso debe tener al menos 10 caracteres."

        prioridad = (datos.get("prioridad") or "Normal").strip()
        if prioridad not in PRIORIDADES_AVISO:
            prioridad = "Normal"

        sec_str = datos.get("id_sector")
        id_sector = int(sec_str) if sec_str and str(sec_str).strip().isdigit() else None

        id_creado = self._repo.crear_aviso(
            titulo=titulo,
            contenido=contenido,
            prioridad=prioridad,
            id_sector=id_sector,
            activo=1,
        )
        return True, f"Aviso '{titulo}' publicado exitosamente con ID #{id_creado}."

    def alternar_estado_aviso(self, id_aviso: int, rol_usuario: str) -> Tuple[bool, str]:
        """Activa o suspende la visibilidad de un aviso institucional."""
        if not self.validar_acceso_admin(rol_usuario):
            return False, "Acción denegada: Se requieren privilegios de Administrador General."

        exito = self._repo.cambiar_estado_aviso(id_aviso)
        if exito:
            return True, f"Estado del aviso #{id_aviso} actualizado correctamente."
        return False, "No se encontró el aviso solicitado."

    def eliminar_aviso(self, id_aviso: int, rol_usuario: str) -> Tuple[bool, str]:
        """Elimina definitivamente un aviso institucional."""
        if not self.validar_acceso_admin(rol_usuario):
            return False, "Acción denegada: Se requieren privilegios de Administrador General."

        exito = self._repo.eliminar_aviso(id_aviso)
        if exito:
            return True, f"Aviso #{id_aviso} eliminado correctamente."
        return False, "No se encontró el aviso para eliminar."

    # ========================================================================
    # MODERACIÓN DE REPORTES CIUDADANOS
    # ========================================================================

    def moderar_reporte(self, id_reporte: int, nuevo_estado: str, rol_usuario: str) -> Tuple[bool, str]:
        """Actualiza el estado de atención de una incidencia ciudadana."""
        if not self.validar_acceso_admin(rol_usuario):
            return False, "Acción denegada: Se requieren privilegios de Administrador General."

        nuevo_estado = (nuevo_estado or "").strip()
        if nuevo_estado not in ESTADOS_REPORTE_VALIDOS:
            return False, f"Estado inválido. Opciones permitidas: {', '.join(ESTADOS_REPORTE_VALIDOS)}"

        exito = self._repo.actualizar_estado_reporte(id_reporte, nuevo_estado)
        if exito:
            return True, f"Incidencia #{id_reporte} actualizada a '{nuevo_estado}'."
        return False, "No se pudo actualizar el estado de la incidencia."
