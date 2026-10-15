from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Sector:
    """Representación de un sector hidráulico de la red de CMAS."""
    id_sector: int
    nombre: str
    descripcion: Optional[str] = None
    red_hidraulica: Optional[str] = None
    disponibilidad: Optional[str] = "Disponible"


@dataclass(frozen=True)
class Colonia:
    """Representación de una colonia atendida por CMAS Xalapa."""
    id_colonia: int
    nombre: str
    codigo_postal: str
    id_sector: Optional[int] = None
    zona: Optional[str] = None


@dataclass(frozen=True)
class ProgramacionDia:
    """Programación de suministro de agua para un día específico de la semana."""
    id_programacion: int
    id_colonia: int
    dia_semana: str
    hora_inicio: str
    hora_fin: str
    estado_servicio: str  # 'Activo', 'Suspendido', 'Mantenimiento'
    fecha_actualizacion: str

    @property
    def horario_formateado(self) -> str:
        """Devuelve el rango de horario formateado."""
        if self.estado_servicio == "Activo":
            return f"{self.hora_inicio} - {self.hora_fin} hrs"
        elif self.estado_servicio == "Mantenimiento":
            return f"Ventana de maniobras: {self.hora_inicio} - {self.hora_fin} hrs"
        return "Sin suministro programado"


@dataclass
class MetricaFiabilidad:
    """Métricas de fiabilidad y estabilidad del servicio para el sector/colonia."""
    dias_servicio: int
    total_dias: int
    porcentaje_cobertura: float
    horas_totales_semanales: float
    nivel_estabilidad: str  # 'Alta', 'Media', 'En observación'


@dataclass
class ConsultaResultado:
    """Resultado estructurado de una consulta de tandeos."""
    success: bool
    encontrado: bool
    mensaje: str
    colonia: Optional[Colonia] = None
    sector: Optional[Sector] = None
    programacion: List[ProgramacionDia] = field(default_factory=list)
    coincidencias: List[Colonia] = field(default_factory=list)
    fiabilidad: Optional[MetricaFiabilidad] = None
    termino_busqueda: str = ""
