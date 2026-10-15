import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from app.repositories.consulta_repository import ConsultaRepository

DIAS_SEMANA_ORDEN = [
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
]


class ConsultaService:
    """Lógica de negocio para la búsqueda, validación y consulta de tandeos de agua."""

    def __init__(self, repo: Optional[ConsultaRepository] = None) -> None:
        self._repo = repo or ConsultaRepository()

    def validar_termino(self, termino: str) -> Optional[str]:
        """Valida las reglas de negocio del término de búsqueda.
        - Si es puramente numérico, debe constar exactamente de 5 dígitos (Código Postal).
        - Si es alfanumérico o texto, debe contener al menos 2 caracteres útiles.
        Retorna None si es válido o un mensaje de error explicativo si no lo es.
        """
        limpio = (termino or "").strip()
        if not limpio:
            return "Por favor ingrese al menos 2 caracteres o un código postal de 5 dígitos."

        # Validación si es numérico (Código Postal)
        if limpio.isdigit():
            if len(limpio) != 5:
                return "El código postal debe contener exactamente 5 dígitos numéricos (ej. 91000)."
            return None

        # Validación si es texto
        if len(limpio) < 2:
            return "Por favor ingrese al menos 2 caracteres para realizar la búsqueda de colonia."

        return None

    def _calcular_horas(self, hora_inicio: str, hora_fin: str) -> float:
        """Calcula la duración en horas entre hora_inicio y hora_fin (HH:MM)."""
        try:
            h_ini, m_ini = map(int, hora_inicio.split(":"))
            h_fin, m_fin = map(int, hora_fin.split(":"))
            minutos = (h_fin * 60 + m_fin) - (h_ini * 60 + m_ini)
            return max(0.0, round(minutos / 60.0, 1))
        except Exception:
            return 0.0

    def _formatear_fecha(self, fecha_str: Optional[str]) -> str:
        """Formatea la fecha de actualización a un formato legible en español."""
        if not fecha_str:
            return datetime.now().strftime("%d/%m/%Y %H:%M hrs")
        try:
            # Soportar formatos SQLite datetime ('YYYY-MM-DD HH:MM:SS')
            dt = datetime.fromisoformat(fecha_str.replace(" ", "T"))
            meses = [
                "enero", "febrero", "marzo", "abril", "mayo", "junio",
                "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
            ]
            return f"{dt.day} de {meses[dt.month - 1]} de {dt.year}, {dt.strftime('%H:%M')} hrs"
        except Exception:
            return fecha_str

    def _calcular_fiabilidad(self, programacion: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calcula la métrica de fiabilidad y disponibilidad del suministro de agua."""
        if not programacion:
            return {
                "dias_servicio": 0,
                "total_dias": 0,
                "porcentaje_cobertura": 0.0,
                "horas_totales_semanales": 0.0,
                "nivel_estabilidad": "Sin datos",
                "badge_clase": "secondary",
                "descripcion": "Sin programación registrada",
            }

        total_dias = len(programacion)
        dias_activos = sum(1 for p in programacion if p.get("estado_servicio") == "Activo")
        dias_mantenimiento = sum(1 for p in programacion if p.get("estado_servicio") == "Mantenimiento")

        horas_totales = sum(
            self._calcular_horas(p.get("hora_inicio", "00:00"), p.get("hora_fin", "00:00"))
            for p in programacion
            if p.get("estado_servicio") == "Activo"
        )

        porcentaje = round((dias_activos / max(1, total_dias)) * 100, 1)

        if porcentaje >= 50:
            nivel = "Alta Disponibilidad"
            badge = "success"
            desc = f"Servicio activo {dias_activos} de {total_dias} días semanales con red estable."
        elif porcentaje >= 28:
            nivel = "Suministro Programado"
            badge = "info"
            desc = f"Servicio activo {dias_activos} de {total_dias} días semanales según tandeo."
        elif dias_mantenimiento > 0:
            nivel = "Zona en Maniobras"
            badge = "warning"
            desc = "Red en mantenimiento preventivo o correctivo."
        else:
            nivel = "Suministro Restringido"
            badge = "danger"
            desc = "Servicio limitado por estiaje o mantenimiento."

        return {
            "dias_servicio": dias_activos,
            "total_dias": total_dias,
            "porcentaje_cobertura": porcentaje,
            "horas_totales_semanales": horas_totales,
            "nivel_estabilidad": nivel,
            "badge_clase": badge,
            "descripcion": desc,
        }

    def _ordenar_cronologicamente(self, programacion: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Garantiza que la programación esté estrictamente ordenada de Lunes a Domingo y formatea horas."""
        orden_dict = {dia: i for i, dia in enumerate(DIAS_SEMANA_ORDEN)}

        def clave_orden(item: Dict[str, Any]) -> int:
            dia = item.get("dia_semana", "")
            return orden_dict.get(dia, 99)

        lista_ordenada = sorted(programacion, key=clave_orden)

        # Formateo de horas y enriquecimiento
        for item in lista_ordenada:
            h_ini = (item.get("hora_inicio") or "").strip()
            h_fin = (item.get("hora_fin") or "").strip()

            # Normalizar HH:MM
            if len(h_ini) == 4 and ":" in h_ini:
                h_ini = f"0{h_ini}"
            if len(h_fin) == 4 and ":" in h_fin:
                h_fin = f"0{h_fin}"

            item["hora_inicio"] = h_ini or "00:00"
            item["hora_fin"] = h_fin or "23:59"

            # Formato fecha legible
            f_act = item.get("fecha_actualizacion")
            item["fecha_actualizacion_legible"] = self._formatear_fecha(f_act)

        return lista_ordenada

    def consultar_por_termino(self, termino: str) -> Dict[str, Any]:
        """Consulta el sector y la programación semanal asociada a una colonia o CP."""
        termino_limpio = (termino or "").strip()

        # Validación de reglas de negocio
        error_validacion = self.validar_termino(termino_limpio)
        if error_validacion:
            return {
                "success": False,
                "encontrado": False,
                "mensaje": error_validacion,
                "colonia": None,
                "sector": None,
                "programacion": [],
                "coincidencias": [],
                "fiabilidad": None,
                "termino": termino_limpio,
            }

        # Ejecución de la consulta unificada (JOIN colonias + sectores + programacion_tandeos)
        resultado_db = self._repo.consultar_unificada(termino_limpio, limite=10)

        if not resultado_db or not resultado_db.get("colonia"):
            return {
                "success": True,
                "encontrado": False,
                "mensaje": f'No encontramos resultados para "{termino_limpio}". Verifique el nombre o código postal.',
                "colonia": None,
                "sector": None,
                "programacion": [],
                "coincidencias": [],
                "fiabilidad": None,
                "termino": termino_limpio,
            }

        colonia = resultado_db["colonia"]
        sector = resultado_db["sector"]
        programacion_cruda = resultado_db.get("programacion", [])
        coincidencias = resultado_db.get("coincidencias", [])

        # Ordenamiento cronológico de Lunes a Domingo y formateo
        programacion_ordenada = self._ordenar_cronologicamente(programacion_cruda)

        # Métrica de fiabilidad
        fiabilidad = self._calcular_fiabilidad(programacion_ordenada)

        # Fecha de última actualización general
        ultima_fecha = (
            programacion_ordenada[0].get("fecha_actualizacion_legible")
            if programacion_ordenada
            else self._formatear_fecha(None)
        )

        return {
            "success": True,
            "encontrado": True,
            "mensaje": "Consulta realizada con éxito.",
            "colonia": colonia,
            "sector": sector,
            "programacion": programacion_ordenada,
            "coincidencias": coincidencias,
            "fiabilidad": fiabilidad,
            "ultima_actualizacion": ultima_fecha,
            "termino": termino_limpio,
        }
