"""
Repositorio de datos para el módulo de Supervisión y Operación Técnica CMAS.
Todas las consultas a database/tandeos.db son estrictamente parametrizadas mediante placeholders (?).
"""

from typing import List, Dict, Any, Optional, Tuple
from app.repositories.db import get_db


class SupervisorRepository:
    """Capa de persistencia y agregaciones para el panel de supervisión."""

    def contar_metricas_globales(self, filtros: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calcula los totales de reportes abiertos, en proceso, cerrados y del día actual."""
        db = get_db()
        filtros = filtros or {}

        clausulas = ["1=1"]
        params: List[Any] = []

        if filtros.get("fecha_inicio"):
            clausulas.append("rc.fecha_hora_reporte >= ?")
            params.append(f"{filtros['fecha_inicio']} 00:00:00")

        if filtros.get("fecha_fin"):
            clausulas.append("rc.fecha_hora_reporte <= ?")
            params.append(f"{filtros['fecha_fin']} 23:59:59")

        if filtros.get("id_sector"):
            clausulas.append("c.id_sector = ?")
            params.append(int(filtros["id_sector"]))

        if filtros.get("id_colonia"):
            clausulas.append("rc.id_colonia = ?")
            params.append(int(filtros["id_colonia"]))

        if filtros.get("tipo_incidencia"):
            clausulas.append("rc.tipo_incidencia = ?")
            params.append(filtros["tipo_incidencia"])

        where_sql = " AND ".join(clausulas)

        query = f"""
            SELECT 
                COUNT(rc.id_reporte) AS total_reportes,
                SUM(CASE WHEN rc.estado = 'Abierto' THEN 1 ELSE 0 END) AS abiertos,
                SUM(CASE WHEN rc.estado = 'En proceso' THEN 1 ELSE 0 END) AS en_proceso,
                SUM(CASE WHEN rc.estado = 'Cerrado' THEN 1 ELSE 0 END) AS cerrados,
                SUM(CASE WHEN date(rc.fecha_hora_reporte) = date('now', 'localtime') THEN 1 ELSE 0 END) AS hoy,
                SUM(CASE WHEN rc.tipo_incidencia = 'Falta de agua' THEN 1 ELSE 0 END) AS falta_agua,
                SUM(CASE WHEN rc.tipo_incidencia = 'Fuga' THEN 1 ELSE 0 END) AS fugas,
                SUM(CASE WHEN rc.tipo_incidencia = 'Baja presión' THEN 1 ELSE 0 END) AS baja_presion
            FROM reportes_ciudadanos rc
            LEFT JOIN colonias c ON rc.id_colonia = c.id_colonia
            WHERE {where_sql}
        """
        row = db.execute(query, tuple(params)).fetchone()

        total = row["total_reportes"] if row and row["total_reportes"] else 0
        abiertos = row["abiertos"] if row and row["abiertos"] else 0
        en_proceso = row["en_proceso"] if row and row["en_proceso"] else 0
        cerrados = row["cerrados"] if row and row["cerrados"] else 0
        hoy = row["hoy"] if row and row["hoy"] else 0
        falta_agua = row["falta_agua"] if row and row["falta_agua"] else 0
        fugas = row["fugas"] if row and row["fugas"] else 0
        baja_presion = row["baja_presion"] if row and row["baja_presion"] else 0

        tasa_resolucion = round((cerrados / total * 100), 1) if total > 0 else 0.0

        return {
            "total_reportes": total,
            "abiertos": abiertos,
            "en_proceso": en_proceso,
            "cerrados": cerrados,
            "hoy": hoy,
            "falta_agua": falta_agua,
            "fugas": fugas,
            "baja_presion": baja_presion,
            "tasa_resolucion": tasa_resolucion,
        }

    def obtener_sectores_criticos(
        self, filtros: Optional[Dict[str, Any]] = None, limite: int = 5
    ) -> List[Dict[str, Any]]:
        """Identifica los sectores con mayor número de reportes y tasa de criticidad."""
        db = get_db()
        filtros = filtros or {}

        clausulas = ["1=1"]
        params: List[Any] = []

        if filtros.get("fecha_inicio"):
            clausulas.append("(rc.fecha_hora_reporte IS NULL OR rc.fecha_hora_reporte >= ?)")
            params.append(f"{filtros['fecha_inicio']} 00:00:00")

        if filtros.get("fecha_fin"):
            clausulas.append("(rc.fecha_hora_reporte IS NULL OR rc.fecha_hora_reporte <= ?)")
            params.append(f"{filtros['fecha_fin']} 23:59:59")

        where_sql = " AND ".join(clausulas)

        query = f"""
            SELECT 
                s.id_sector,
                s.nombre AS nombre_sector,
                s.descripcion AS sector_descripcion,
                COUNT(rc.id_reporte) AS total_reportes,
                SUM(CASE WHEN rc.estado = 'Abierto' THEN 1 ELSE 0 END) AS abiertos,
                SUM(CASE WHEN rc.estado = 'En proceso' THEN 1 ELSE 0 END) AS en_proceso,
                SUM(CASE WHEN rc.estado = 'Cerrado' THEN 1 ELSE 0 END) AS cerrados,
                SUM(CASE WHEN rc.tipo_incidencia = 'Falta de agua' THEN 1 ELSE 0 END) AS faltas_agua,
                SUM(CASE WHEN rc.tipo_incidencia = 'Fuga' THEN 1 ELSE 0 END) AS fugas,
                SUM(CASE WHEN rc.tipo_incidencia = 'Baja presión' THEN 1 ELSE 0 END) AS bajas_presion
            FROM sectores s
            LEFT JOIN colonias c ON s.id_sector = c.id_sector
            LEFT JOIN reportes_ciudadanos rc ON c.id_colonia = rc.id_colonia AND {where_sql}
            GROUP BY s.id_sector, s.nombre, s.descripcion
            ORDER BY abiertos DESC, total_reportes DESC
            LIMIT ?
        """
        params.append(limite)
        rows = db.execute(query, tuple(params)).fetchall()

        resultado = []
        for r in rows:
            tot = r["total_reportes"] or 0
            ab = r["abiertos"] or 0
            en_p = r["en_proceso"] or 0
            cerr = r["cerrados"] or 0
            resultado.append({
                "id_sector": r["id_sector"],
                "nombre_sector": r["nombre_sector"],
                "descripcion": r["sector_descripcion"],
                "total_reportes": tot,
                "abiertos": ab,
                "en_proceso": en_p,
                "cerrados": cerr,
                "faltas_agua": r["faltas_agua"] or 0,
                "fugas": r["fugas"] or 0,
                "bajas_presion": r["bajas_presion"] or 0,
                "tasa_atencion": round((cerr / tot * 100), 1) if tot > 0 else 100.0,
            })
        return resultado

    def obtener_discrepancias_tandeo(
        self, filtros: Optional[Dict[str, Any]] = None, limite: int = 25
    ) -> List[Dict[str, Any]]:
        """
        Detecta anomalías cruzando programación oficial con reportes ciudadanos:
        Colonias con reporte de 'Falta de agua' en un día que tenían tandeo 'Activo'.
        """
        db = get_db()
        filtros = filtros or {}

        clausulas = [
            "rc.tipo_incidencia = 'Falta de agua'",
            "pt.estado_servicio = 'Activo'",
            """pt.dia_semana = (
                CASE CAST(strftime('%w', rc.fecha_hora_reporte) AS INTEGER)
                    WHEN 0 THEN 'Domingo'
                    WHEN 1 THEN 'Lunes'
                    WHEN 2 THEN 'Martes'
                    WHEN 3 THEN 'Miércoles'
                    WHEN 4 THEN 'Jueves'
                    WHEN 5 THEN 'Viernes'
                    WHEN 6 THEN 'Sábado'
                END
            )""",
        ]
        params: List[Any] = []

        if filtros.get("fecha_inicio"):
            clausulas.append("rc.fecha_hora_reporte >= ?")
            params.append(f"{filtros['fecha_inicio']} 00:00:00")

        if filtros.get("fecha_fin"):
            clausulas.append("rc.fecha_hora_reporte <= ?")
            params.append(f"{filtros['fecha_fin']} 23:59:59")

        if filtros.get("id_sector"):
            clausulas.append("c.id_sector = ?")
            params.append(int(filtros["id_sector"]))

        if filtros.get("id_colonia"):
            clausulas.append("rc.id_colonia = ?")
            params.append(int(filtros["id_colonia"]))

        if filtros.get("estado"):
            clausulas.append("rc.estado = ?")
            params.append(filtros["estado"])

        where_sql = " AND ".join(clausulas)

        query = f"""
            SELECT 
                rc.id_reporte,
                rc.folio,
                rc.tipo_incidencia,
                rc.descripcion,
                rc.fecha_hora_reporte,
                rc.estado,
                c.id_colonia,
                c.nombre AS nombre_colonia,
                c.codigo_postal,
                c.zona,
                s.id_sector,
                s.nombre AS nombre_sector,
                pt.dia_semana,
                pt.hora_inicio,
                pt.hora_fin,
                pt.estado_servicio AS programacion_oficial
            FROM reportes_ciudadanos rc
            INNER JOIN colonias c ON rc.id_colonia = c.id_colonia
            INNER JOIN sectores s ON c.id_sector = s.id_sector
            INNER JOIN programacion_tandeos pt ON c.id_colonia = pt.id_colonia
            WHERE {where_sql}
            ORDER BY rc.fecha_hora_reporte DESC
            LIMIT ?
        """
        params.append(limite)
        rows = db.execute(query, tuple(params)).fetchall()

        resultado = []
        for r in rows:
            resultado.append({
                "id_reporte": r["id_reporte"],
                "folio": r["folio"],
                "colonia": r["nombre_colonia"],
                "id_colonia": r["id_colonia"],
                "codigo_postal": r["codigo_postal"],
                "zona": r["zona"],
                "sector": r["nombre_sector"],
                "id_sector": r["id_sector"],
                "dia_semana": r["dia_semana"],
                "horario_programado": f"{r['hora_inicio']} - {r['hora_fin']}",
                "estado_reporte": r["estado"],
                "fecha_hora_reporte": r["fecha_hora_reporte"],
                "descripcion": r["descripcion"],
                "severidad": "Anomalía Crítica" if r["estado"] == "Abierto" else "En Verificación",
            })
        return resultado

    def obtener_colonias_anomalias(
        self, filtros: Optional[Dict[str, Any]] = None, limite: int = 10
    ) -> List[Dict[str, Any]]:
        """Lista las colonias con mayor recurrencia de incidencias registradas."""
        db = get_db()
        filtros = filtros or {}

        clausulas = ["1=1"]
        params: List[Any] = []

        if filtros.get("fecha_inicio"):
            clausulas.append("rc.fecha_hora_reporte >= ?")
            params.append(f"{filtros['fecha_inicio']} 00:00:00")

        if filtros.get("fecha_fin"):
            clausulas.append("rc.fecha_hora_reporte <= ?")
            params.append(f"{filtros['fecha_fin']} 23:59:59")

        if filtros.get("id_sector"):
            clausulas.append("c.id_sector = ?")
            params.append(int(filtros["id_sector"]))

        if filtros.get("tipo_incidencia"):
            clausulas.append("rc.tipo_incidencia = ?")
            params.append(filtros["tipo_incidencia"])

        where_sql = " AND ".join(clausulas)

        query = f"""
            SELECT 
                c.id_colonia,
                c.nombre AS nombre_colonia,
                c.codigo_postal,
                c.zona,
                s.id_sector,
                s.nombre AS nombre_sector,
                COUNT(rc.id_reporte) AS total_incidencias,
                SUM(CASE WHEN rc.estado = 'Abierto' THEN 1 ELSE 0 END) AS abiertas,
                SUM(CASE WHEN rc.estado = 'En proceso' THEN 1 ELSE 0 END) AS en_proceso,
                SUM(CASE WHEN rc.estado = 'Cerrado' THEN 1 ELSE 0 END) AS resueltas,
                SUM(CASE WHEN rc.tipo_incidencia = 'Falta de agua' THEN 1 ELSE 0 END) AS falta_agua,
                SUM(CASE WHEN rc.tipo_incidencia = 'Fuga' THEN 1 ELSE 0 END) AS fugas,
                MAX(rc.fecha_hora_reporte) AS ultima_incidencia
            FROM colonias c
            INNER JOIN reportes_ciudadanos rc ON c.id_colonia = rc.id_colonia
            LEFT JOIN sectores s ON c.id_sector = s.id_sector
            WHERE {where_sql}
            GROUP BY c.id_colonia, c.nombre, c.codigo_postal, c.zona, s.id_sector, s.nombre
            ORDER BY total_incidencias DESC, abiertas DESC
            LIMIT ?
        """
        params.append(limite)
        rows = db.execute(query, tuple(params)).fetchall()

        resultado = []
        for r in rows:
            resultado.append({
                "id_colonia": r["id_colonia"],
                "nombre_colonia": r["nombre_colonia"],
                "codigo_postal": r["codigo_postal"],
                "zona": r["zona"],
                "nombre_sector": r["nombre_sector"],
                "total_incidencias": r["total_incidencias"],
                "abiertas": r["abiertas"] or 0,
                "en_proceso": r["en_proceso"] or 0,
                "resueltas": r["resueltas"] or 0,
                "falta_agua": r["falta_agua"] or 0,
                "fugas": r["fugas"] or 0,
                "ultima_incidencia": r["ultima_incidencia"],
            })
        return resultado

    def listar_incidencias_filtradas(
        self, filtros: Optional[Dict[str, Any]] = None, limite: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Obtiene la lista detallada de incidencias ciudadanas aplicando filtros dinámicos parametrizados."""
        db = get_db()
        filtros = filtros or {}

        clausulas = ["1=1"]
        params: List[Any] = []

        if filtros.get("fecha_inicio"):
            clausulas.append("rc.fecha_hora_reporte >= ?")
            params.append(f"{filtros['fecha_inicio']} 00:00:00")

        if filtros.get("fecha_fin"):
            clausulas.append("rc.fecha_hora_reporte <= ?")
            params.append(f"{filtros['fecha_fin']} 23:59:59")

        if filtros.get("id_sector"):
            clausulas.append("c.id_sector = ?")
            params.append(int(filtros["id_sector"]))

        if filtros.get("id_colonia"):
            clausulas.append("rc.id_colonia = ?")
            params.append(int(filtros["id_colonia"]))

        if filtros.get("tipo_incidencia"):
            clausulas.append("rc.tipo_incidencia = ?")
            params.append(filtros["tipo_incidencia"])

        if filtros.get("estado"):
            clausulas.append("rc.estado = ?")
            params.append(filtros["estado"])

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
                c.zona,
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

        resultado = []
        for r in rows:
            resultado.append({
                "id_reporte": r["id_reporte"],
                "folio": r["folio"],
                "tipo_incidencia": r["tipo_incidencia"],
                "descripcion": r["descripcion"],
                "nombre_ciudadano": r["nombre_ciudadano"] or "Anónimo",
                "telefono_contacto": r["telefono_contacto"] or "No proporcionado",
                "fecha_hora_reporte": r["fecha_hora_reporte"],
                "estado": r["estado"],
                "id_colonia": r["id_colonia"],
                "nombre_colonia": r["nombre_colonia"],
                "codigo_postal": r["codigo_postal"],
                "zona": r["zona"],
                "id_sector": r["id_sector"],
                "nombre_sector": r["nombre_sector"],
            })
        return resultado

    def actualizar_estado_reporte(self, id_reporte: int, nuevo_estado: str) -> bool:
        """Actualiza el estado operativo de una incidencia ciudadana mediante consulta parametrizada."""
        db = get_db()
        cur = db.execute(
            "UPDATE reportes_ciudadanos SET estado = ? WHERE id_reporte = ?",
            (nuevo_estado, id_reporte),
        )
        db.commit()
        return cur.rowcount > 0

    def obtener_reporte_por_id(self, id_reporte: int) -> Optional[Dict[str, Any]]:
        """Obtiene una incidencia por su ID primario."""
        db = get_db()
        row = db.execute(
            """
            SELECT 
                rc.id_reporte, rc.folio, rc.id_colonia, rc.tipo_incidencia,
                rc.descripcion, rc.estado, rc.fecha_hora_reporte,
                c.nombre AS nombre_colonia, c.codigo_postal
            FROM reportes_ciudadanos rc
            LEFT JOIN colonias c ON rc.id_colonia = c.id_colonia
            WHERE rc.id_reporte = ?
            LIMIT 1
            """,
            (id_reporte,),
        ).fetchone()
        if not row:
            return None
        return dict(row)

    def registrar_bitacora(
        self,
        id_usuario: int,
        accion: str,
        folio_reporte: Optional[str] = None,
        id_colonia: Optional[int] = None,
        observaciones: Optional[str] = None,
    ) -> bool:
        """Registra un evento o acción en la bitácora del supervisor."""
        db = get_db()
        # Verificar si la tabla bitacora_supervisor existe
        cur_check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='bitacora_supervisor'"
        )
        if not cur_check.fetchone():
            return False

        cur = db.execute(
            """
            INSERT INTO bitacora_supervisor (id_usuario, accion, folio_reporte, id_colonia, observaciones)
            VALUES (?, ?, ?, ?, ?)
            """,
            (id_usuario, accion, folio_reporte, id_colonia, observaciones or ""),
        )
        db.commit()
        return cur.rowcount > 0

    def listar_bitacora_reciente(self, limite: int = 15) -> List[Dict[str, Any]]:
        """Retorna las acciones más recientes registradas por el personal supervisor."""
        db = get_db()
        cur_check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='bitacora_supervisor'"
        )
        if not cur_check.fetchone():
            return []

        rows = db.execute(
            """
            SELECT 
                b.id_bitacora, b.accion, b.folio_reporte, b.observaciones, b.fecha_hora,
                u.nombre AS nombre_usuario, u.rol AS rol_usuario
            FROM bitacora_supervisor b
            LEFT JOIN Usuario u ON b.id_usuario = u.id_usuario
            ORDER BY b.fecha_hora DESC
            LIMIT ?
            """,
            (limite,),
        ).fetchall()
        return [dict(r) for r in rows]

    def listar_sectores_catalogo(self) -> List[Dict[str, Any]]:
        """Lista el catálogo de sectores oficiales de Xalapa para selectores de filtro."""
        db = get_db()
        rows = db.execute(
            "SELECT id_sector, nombre, descripcion FROM sectores ORDER BY id_sector ASC"
        ).fetchall()
        return [dict(r) for r in rows]

    def listar_colonias_catalogo(self, id_sector: Optional[int] = None) -> List[Dict[str, Any]]:
        """Lista colonias para selectores de filtro, opcionalmente acotadas por sector."""
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
