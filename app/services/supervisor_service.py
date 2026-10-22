"""
Servicio de negocio para el módulo de Supervisión y Operación Técnica CMAS.
Maneja reglas de control de acceso por rol, cálculo de indicadores de confiabilidad,
detección de discrepancias en tandeos y gestión de estados de incidencias.
"""

from typing import Dict, Any, List, Optional, Tuple
from app.repositories.supervisor_repository import SupervisorRepository

ROLES_SUPERVISOR_PERMITIDOS = {"Supervisor", "Tecnico", "Técnico", "Operador"}
ESTADOS_REPORTE_PERMITIDOS = {"Abierto", "En proceso", "Cerrado"}


class SupervisorService:
    """Lógica de análisis y gestión de anomalías operativas para supervisores."""

    def __init__(self, repository: Optional[SupervisorRepository] = None):
        self._repo = repository or SupervisorRepository()

    def validar_acceso_supervisor(self, rol: Optional[str]) -> bool:
        """
        Valida que el usuario posea credencial operativa ('Supervisor' o 'Técnico').
        Bloquea a usuarios con rol 'Ciudadano' o no autenticados.
        """
        if not rol:
            return False
        return rol in ROLES_SUPERVISOR_PERMITIDOS

    def normalizar_filtros(self, raw_filtros: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Limpia y valida los parámetros de filtro ingresados en la interfaz o petición."""
        if not raw_filtros:
            return {}

        filtros: Dict[str, Any] = {}

        # Sector
        sec = raw_filtros.get("id_sector") or raw_filtros.get("sector")
        if sec and str(sec).strip().isdigit():
            filtros["id_sector"] = int(sec)

        # Colonia
        col = raw_filtros.get("id_colonia") or raw_filtros.get("colonia")
        if col and str(col).strip().isdigit():
            filtros["id_colonia"] = int(col)

        # Tipo de Incidencia
        tipo = (raw_filtros.get("tipo_incidencia") or raw_filtros.get("tipo") or "").strip()
        if tipo and tipo != "Todos":
            filtros["tipo_incidencia"] = tipo

        # Estado
        estado = (raw_filtros.get("estado") or "").strip()
        if estado and estado in ESTADOS_REPORTE_PERMITIDOS:
            filtros["estado"] = estado

        # Fechas
        f_ini = (raw_filtros.get("fecha_inicio") or "").strip()
        if f_ini and len(f_ini) >= 10:
            filtros["fecha_inicio"] = f_ini[:10]

        f_fin = (raw_filtros.get("fecha_fin") or "").strip()
        if f_fin and len(f_fin) >= 10:
            filtros["fecha_fin"] = f_fin[:10]

        return filtros

    def obtener_dashboard(self, raw_filtros: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calcula y compila toda la información requerida por el Dashboard de Supervisión:
        - KPIs consolidados y tasa de resolución
        - Detección de discrepancias operativas (tandeo Activo vs Falta de agua)
        - Sectores críticos ordenados por gravedad
        - Colonias con mayor índice de anomalías
        - Listado de incidencias filtradas y bitácora de acciones
        """
        filtros = self.normalizar_filtros(raw_filtros)

        kpis = self._repo.contar_metricas_globales(filtros)
        sectores_criticos = self._repo.obtener_sectores_criticos(filtros, limite=6)
        discrepancias = self._repo.obtener_discrepancias_tandeo(filtros, limite=30)
        colonias_anomalias = self._repo.obtener_colonias_anomalias(filtros, limite=10)
        incidencias = self._repo.listar_incidencias_filtradas(filtros, limite=50)

        # Tasa de discrepancia respecto a reportes por falta de agua
        total_falta_agua = kpis.get("falta_agua", 0)
        total_disc = len(discrepancias)
        tasa_discrepancia = (
            round((total_disc / total_falta_agua * 100), 1) if total_falta_agua > 0 else 0.0
        )
        kpis["total_discrepancias"] = total_disc
        kpis["tasa_discrepancia"] = tasa_discrepancia

        # Catálogos para selectores
        sectores_catalogo = self._repo.listar_sectores_catalogo()
        id_sec = filtros.get("id_sector")
        colonias_catalogo = self._repo.listar_colonias_catalogo(id_sec)
        bitacora = self._repo.listar_bitacora_reciente(limite=10)

        return {
            "kpis": kpis,
            "sectores_criticos": sectores_criticos,
            "discrepancias": discrepancias,
            "colonias_anomalias": colonias_anomalias,
            "incidencias": incidencias,
            "sectores_catalogo": sectores_catalogo,
            "colonias_catalogo": colonias_catalogo,
            "bitacora": bitacora,
            "filtros_aplicados": filtros,
        }

    def cambiar_estado_reporte(
        self,
        id_reporte: int,
        nuevo_estado: str,
        id_usuario: int,
        rol_usuario: str,
        observaciones: str = "",
    ) -> Tuple[bool, str]:
        """
        Permite al personal técnico o supervisor actualizar el estado de una incidencia
        (Abierto -> En proceso -> Cerrado), asentando el evento en la bitácora operativa.
        """
        # 1. Verificación de rol operativo
        if not self.validar_acceso_supervisor(rol_usuario):
            return False, "Permiso denegado: Acción reservada a Supervisores y Técnicos."

        # 2. Validación de estado
        nuevo_estado = (nuevo_estado or "").strip()
        if nuevo_estado not in ESTADOS_REPORTE_PERMITIDOS:
            return False, f"Estado '{nuevo_estado}' inválido. Valores permitidos: {', '.join(ESTADOS_REPORTE_PERMITIDOS)}"

        # 3. Comprobar existencia
        reporte = self._repo.obtener_reporte_por_id(id_reporte)
        if not reporte:
            return False, f"No se encontró el reporte con identificador #{id_reporte}"

        estado_anterior = reporte["estado"]
        if estado_anterior == nuevo_estado:
            return True, f"El reporte ya se encuentra en estado '{nuevo_estado}'."

        # 4. Actualización en repositorio
        exito = self._repo.actualizar_estado_reporte(id_reporte, nuevo_estado)
        if not exito:
            return False, "Ocurrió un error al intentar actualizar el estado en base de datos."

        # 5. Registro en bitácora
        detalle_accion = f"Cambio de estado: {estado_anterior} -> {nuevo_estado}"
        obs_final = observaciones.strip() if observaciones else "Actualización operativa desde panel de supervisor."
        self._repo.registrar_bitacora(
            id_usuario=id_usuario,
            accion=detalle_accion,
            folio_reporte=reporte["folio"],
            id_colonia=reporte["id_colonia"],
            observaciones=obs_final,
        )

        return True, f"Reporte {reporte['folio']} actualizado a '{nuevo_estado}' exitosamente."
