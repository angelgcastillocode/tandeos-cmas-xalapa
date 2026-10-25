"""
Repositorio de datos para el Panel de Administración General de CMAS Tandeos.
Todas las consultas contra database/tandeos.db son estrictamente parametrizadas mediante placeholders (?).
"""

from typing import List, Dict, Any, Optional, Tuple
from app.repositories.db import get_db


class AdminRepository:
    """Capa de persistencia para la gestión administrativa de CMAS."""

    def __init__(self):
        self._garantizar_tabla_avisos()

    def _garantizar_tabla_avisos(self) -> None:
        """Garantiza la existencia de la tabla de avisos y alertas institucionales."""
        db = get_db()
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS avisos (
                id_aviso INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                contenido TEXT NOT NULL,
                prioridad TEXT NOT NULL DEFAULT 'Normal' CHECK (prioridad IN ('Baja', 'Normal', 'Alta', 'Urgente')),
                id_sector INTEGER,
                activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
                fecha_publicacion DATETIME NOT NULL DEFAULT (DATETIME('now', 'localtime')),
                FOREIGN KEY (id_sector) REFERENCES sectores(id_sector) ON UPDATE CASCADE ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_avisos_activo ON avisos(activo, fecha_publicacion);
            """
        )
        db.commit()

    # ========================================================================
    # 1. MÉTRICAS GENERALES DEL SISTEMA
    # ========================================================================

    def obtener_metricas_generales(self) -> Dict[str, Any]:
        """Calcula indicadores globales del sistema para el panel de administración."""
        db = get_db()

        # Total Colonias
        col_row = db.execute("SELECT COUNT(*) AS total FROM colonias").fetchone()
        total_colonias = col_row["total"] if col_row else 0

        # Total Sectores
        sec_row = db.execute("SELECT COUNT(*) AS total FROM sectores").fetchone()
        total_sectores = sec_row["total"] if sec_row else 0

        # Programaciones de tandeo
        prog_row = db.execute(
            """
            SELECT 
                COUNT(*) AS total,
                SUM(CASE WHEN estado_servicio = 'Activo' THEN 1 ELSE 0 END) AS activos,
                SUM(CASE WHEN estado_servicio = 'Suspendido' THEN 1 ELSE 0 END) AS suspendidos,
                SUM(CASE WHEN estado_servicio = 'Mantenimiento' THEN 1 ELSE 0 END) AS mantenimiento
            FROM programacion_tandeos
            """
        ).fetchone()

        total_tandeos = prog_row["total"] if prog_row and prog_row["total"] else 0
        tandeos_activos = prog_row["activos"] if prog_row and prog_row["activos"] else 0
        tandeos_suspendidos = prog_row["suspendidos"] if prog_row and prog_row["suspendidos"] else 0
        tandeos_mantenimiento = prog_row["mantenimiento"] if prog_row and prog_row["mantenimiento"] else 0

        # Reportes ciudadanos
        total_reportes, reportes_abiertos, reportes_en_proceso, reportes_cerrados = 0, 0, 0, 0
        cur_check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='reportes_ciudadanos'"
        )
        if cur_check.fetchone():
            rep_row = db.execute(
                """
                SELECT 
                    COUNT(*) AS total,
                    SUM(CASE WHEN estado = 'Abierto' THEN 1 ELSE 0 END) AS abiertos,
                    SUM(CASE WHEN estado = 'En proceso' THEN 1 ELSE 0 END) AS en_proceso,
                    SUM(CASE WHEN estado = 'Cerrado' THEN 1 ELSE 0 END) AS cerrados
                FROM reportes_ciudadanos
                """
            ).fetchone()
            if rep_row:
                total_reportes = rep_row["total"] or 0
                reportes_abiertos = rep_row["abiertos"] or 0
                reportes_en_proceso = rep_row["en_proceso"] or 0
                reportes_cerrados = rep_row["cerrados"] or 0

        # Avisos activos
        avisos_row = db.execute("SELECT COUNT(*) AS total FROM avisos WHERE activo = 1").fetchone()
        avisos_activos = avisos_row["total"] if avisos_row else 0

        return {
            "total_colonias": total_colonias,
            "total_sectores": total_sectores,
            "total_tandeos": total_tandeos,
            "tandeos_activos": tandeos_activos,
            "tandeos_suspendidos": tandeos_suspendidos,
            "tandeos_mantenimiento": tandeos_mantenimiento,
            "total_reportes": total_reportes,
            "reportes_abiertos": reportes_abiertos,
            "reportes_en_proceso": reportes_en_proceso,
            "reportes_cerrados": reportes_cerrados,
            "avisos_activos": avisos_activos,
        }

    # ========================================================================
    # 2. GESTIÓN DE CALENDARIOS Y TANDEOS POR COLONIA
    # ========================================================================

    def listar_programaciones(
        self,
        id_sector: Optional[int] = None,
        id_colonia: Optional[int] = None,
        termino: Optional[str] = None,
        limite: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Lista la programación oficial de tandeos con filtros opcionales parametrizados."""
        db = get_db()
        clausulas = ["1=1"]
        params: List[Any] = []

        if id_sector:
            clausulas.append("c.id_sector = ?")
            params.append(int(id_sector))

        if id_colonia:
            clausulas.append("pt.id_colonia = ?")
            params.append(int(id_colonia))

        if termino:
            clausulas.append("(c.nombre LIKE ? OR c.codigo_postal LIKE ?)")
            params.extend([f"%{termino}%", f"%{termino}%"])

        where_sql = " AND ".join(clausulas)

        query = f"""
            SELECT 
                pt.id_programacion,
                pt.id_colonia,
                c.nombre AS nombre_colonia,
                c.codigo_postal,
                c.zona,
                s.id_sector,
                s.nombre AS nombre_sector,
                pt.dia_semana,
                pt.hora_inicio,
                pt.hora_fin,
                pt.estado_servicio,
                pt.fecha_actualizacion
            FROM programacion_tandeos pt
            INNER JOIN colonias c ON pt.id_colonia = c.id_colonia
            LEFT JOIN sectores s ON c.id_sector = s.id_sector
            WHERE {where_sql}
            ORDER BY 
                c.nombre ASC,
                CASE pt.dia_semana
                    WHEN 'Lunes' THEN 1
                    WHEN 'Martes' THEN 2
                    WHEN 'Miércoles' THEN 3
                    WHEN 'Jueves' THEN 4
                    WHEN 'Viernes' THEN 5
                    WHEN 'Sábado' THEN 6
                    WHEN 'Domingo' THEN 7
                    ELSE 8
                END,
                pt.hora_inicio ASC
            LIMIT ? OFFSET ?
        """
        params.extend([limite, offset])
        rows = db.execute(query, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def guardar_programacion_tandeo(
        self,
        id_colonia: int,
        dia_semana: str,
        hora_inicio: str,
        hora_fin: str,
        estado_servicio: str,
    ) -> Tuple[bool, str]:
        """
        Crea o actualiza el registro de tandeo para una colonia y día específico.
        Aplica validaciones y consultas parametrizadas.
        """
        db = get_db()

        # Verificar si la colonia existe
        col = db.execute(
            "SELECT id_colonia, nombre FROM colonias WHERE id_colonia = ?",
            (id_colonia,),
        ).fetchone()
        if not col:
            return False, f"La colonia con ID #{id_colonia} no existe."

        # Buscar si ya existe programación para ese día
        existente = db.execute(
            "SELECT id_programacion FROM programacion_tandeos WHERE id_colonia = ? AND dia_semana = ?",
            (id_colonia, dia_semana),
        ).fetchone()

        if existente:
            db.execute(
                """
                UPDATE programacion_tandeos
                SET hora_inicio = ?, hora_fin = ?, estado_servicio = ?, fecha_actualizacion = datetime('now', 'localtime')
                WHERE id_programacion = ?
                """,
                (hora_inicio, hora_fin, estado_servicio, existente["id_programacion"]),
            )
            accion = "actualizado"
        else:
            db.execute(
                """
                INSERT INTO programacion_tandeos (id_colonia, dia_semana, hora_inicio, hora_fin, estado_servicio)
                VALUES (?, ?, ?, ?, ?)
                """,
                (id_colonia, dia_semana, hora_inicio, hora_fin, estado_servicio),
            )
            accion = "creado"

        db.commit()
        return True, f"Tandeo para {col['nombre']} ({dia_semana}) {accion} exitosamente."

    def eliminar_programacion_tandeo(self, id_programacion: int) -> bool:
        """Elimina una programación de tandeo específica."""
        db = get_db()
        cur = db.execute(
            "DELETE FROM programacion_tandeos WHERE id_programacion = ?",
            (id_programacion,),
        )
        db.commit()
        return cur.rowcount > 0

    # ========================================================================
    # 3. PUBLICACIÓN Y GESTIÓN DE AVISOS INSTITUCIONALES
    # ========================================================================

    def crear_aviso(
        self,
        titulo: str,
        contenido: str,
        prioridad: str = "Normal",
        id_sector: Optional[int] = None,
        activo: int = 1,
    ) -> int:
        """Publica un nuevo aviso o alerta institucional."""
        db = get_db()
        cur = db.execute(
            """
            INSERT INTO avisos (titulo, contenido, prioridad, id_sector, activo)
            VALUES (?, ?, ?, ?, ?)
            """,
            (titulo, contenido, prioridad, id_sector, activo),
        )
        db.commit()
        return cur.lastrowid

    def listar_avisos(
        self, solo_activos: bool = False, id_sector: Optional[int] = None, limite: int = 20
    ) -> List[Dict[str, Any]]:
        """Lista los avisos institucionales registrados."""
        db = get_db()
        clausulas = ["1=1"]
        params: List[Any] = []

        if solo_activos:
            clausulas.append("a.activo = 1")

        if id_sector:
            clausulas.append("(a.id_sector IS NULL OR a.id_sector = ?)")
            params.append(int(id_sector))

        where_sql = " AND ".join(clausulas)
        query = f"""
            SELECT 
                a.id_aviso,
                a.titulo,
                a.contenido,
                a.prioridad,
                a.id_sector,
                s.nombre AS nombre_sector,
                a.activo,
                a.fecha_publicacion
            FROM avisos a
            LEFT JOIN sectores s ON a.id_sector = s.id_sector
            WHERE {where_sql}
            ORDER BY 
                CASE a.prioridad
                    WHEN 'Urgente' THEN 1
                    WHEN 'Alta' THEN 2
                    WHEN 'Normal' THEN 3
                    WHEN 'Baja' THEN 4
                    ELSE 5
                END,
                a.fecha_publicacion DESC
            LIMIT ?
        """
        params.append(limite)
        rows = db.execute(query, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def cambiar_estado_aviso(self, id_aviso: int, nuevo_estado: Optional[int] = None) -> bool:
        """Activa o desactiva un aviso institucional."""
        db = get_db()
        if nuevo_estado is None:
            cur = db.execute(
                "UPDATE avisos SET activo = CASE WHEN activo = 1 THEN 0 ELSE 1 END WHERE id_aviso = ?",
                (id_aviso,),
            )
        else:
            cur = db.execute(
                "UPDATE avisos SET activo = ? WHERE id_aviso = ?",
                (nuevo_estado, id_aviso),
            )
        db.commit()
        return cur.rowcount > 0

    def eliminar_aviso(self, id_aviso: int) -> bool:
        """Elimina un aviso institucional."""
        db = get_db()
        cur = db.execute("DELETE FROM avisos WHERE id_aviso = ?", (id_aviso,))
        db.commit()
        return cur.rowcount > 0

    # ========================================================================
    # 4. MODERACIÓN DE REPORTES CIUDADANOS
    # ========================================================================

    def listar_reportes_moderacion(
        self,
        estado: Optional[str] = None,
        tipo: Optional[str] = None,
        id_sector: Optional[int] = None,
        limite: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Lista incidencias ciudadanas para moderación y resolución."""
        db = get_db()
        clausulas = ["1=1"]
        params: List[Any] = []

        if estado and estado != "Todos":
            clausulas.append("rc.estado = ?")
            params.append(estado)

        if tipo and tipo != "Todos":
            clausulas.append("rc.tipo_incidencia = ?")
            params.append(tipo)

        if id_sector:
            clausulas.append("c.id_sector = ?")
            params.append(int(id_sector))

        where_sql = " AND ".join(clausulas)
        query = f"""
            SELECT 
                rc.id_reporte,
                rc.folio,
                rc.tipo_incidencia,
                rc.descripcion,
                rc.nombre_ciudadano,
                rc.telefono_contacto,
                rc.fecha_hora_reporte,
                rc.estado,
                c.id_colonia,
                c.nombre AS nombre_colonia,
                c.codigo_postal,
                s.id_sector,
                s.nombre AS nombre_sector
            FROM reportes_ciudadanos rc
            LEFT JOIN colonias c ON rc.id_colonia = c.id_colonia
            LEFT JOIN sectores s ON c.id_sector = s.id_sector
            WHERE {where_sql}
            ORDER BY rc.fecha_hora_reporte DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limite, offset])
        rows = db.execute(query, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def actualizar_estado_reporte(self, id_reporte: int, nuevo_estado: str) -> bool:
        """Modera y actualiza el estado operativo global de una incidencia."""
        db = get_db()
        cur = db.execute(
            "UPDATE reportes_ciudadanos SET estado = ? WHERE id_reporte = ?",
            (nuevo_estado, id_reporte),
        )
        db.commit()
        return cur.rowcount > 0

    # ========================================================================
    # 5. CATÁLOGOS AUXILIARES
    # ========================================================================

    def listar_sectores(self) -> List[Dict[str, Any]]:
        """Lista los sectores oficiales de Xalapa."""
        db = get_db()
        rows = db.execute("SELECT id_sector, nombre, descripcion FROM sectores ORDER BY id_sector ASC").fetchall()
        return [dict(r) for r in rows]

    def listar_colonias(self, id_sector: Optional[int] = None) -> List[Dict[str, Any]]:
        """Lista colonias con nombre y código postal."""
        db = get_db()
        if id_sector:
            rows = db.execute(
                "SELECT id_colonia, nombre, codigo_postal, id_sector FROM colonias WHERE id_sector = ? ORDER BY nombre ASC",
                (int(id_sector),),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT id_colonia, nombre, codigo_postal, id_sector FROM colonias ORDER BY nombre ASC LIMIT 400"
            ).fetchall()
        return [dict(r) for r in rows]
