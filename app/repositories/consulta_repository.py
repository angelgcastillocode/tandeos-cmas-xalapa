from typing import Any, Dict, List, Optional
from app.repositories.db import get_db


class ConsultaRepository:
    """Acceso a datos para búsqueda de Colonias, Sectores y Programación de Tandeo.
    Todas las consultas son estrictamente parametrizadas con placeholders (?).
    """

    def consultar_unificada(self, termino: str, limite: int = 10) -> Optional[Dict[str, Any]]:
        """Realiza una consulta unificada mediante JOIN entre colonias, sectores y programacion_tandeos
        en una sola llamada a SQLite para prevenir el problema de consultas N+1.
        Garantiza orden cronológico (Lunes a Domingo) y parametrización estricta (?).
        """
        termino = (termino or "").strip()
        if not termino:
            return None

        db = get_db()
        patron_like = f"%{termino}%"
        patron_prefix = f"{termino}%"

        # Verificar si existe la tabla 'colonias' (nueva estructura)
        cur_check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='colonias'"
        )
        tiene_colonias_nuevas = cur_check.fetchone() is not None

        if tiene_colonias_nuevas:
            # Consulta unificada JOIN colonias + sectores + programacion_tandeos
            query = """
                SELECT 
                    c.id_colonia,
                    c.nombre AS nombre_colonia,
                    c.codigo_postal,
                    c.zona,
                    c.id_sector,
                    s.nombre AS nombre_sector,
                    s.descripcion AS sector_descripcion,
                    pt.id_programacion,
                    pt.dia_semana,
                    pt.hora_inicio,
                    pt.hora_fin,
                    pt.estado_servicio,
                    pt.fecha_actualizacion
                FROM colonias c
                LEFT JOIN sectores s ON c.id_sector = s.id_sector
                LEFT JOIN programacion_tandeos pt ON c.id_colonia = pt.id_colonia
                WHERE c.codigo_postal = ? OR c.nombre LIKE ?
                ORDER BY
                    CASE
                        WHEN c.codigo_postal = ? THEN 1
                        WHEN LOWER(c.nombre) = LOWER(?) THEN 2
                        WHEN LOWER(c.nombre) LIKE LOWER(?) THEN 3
                        ELSE 4
                    END,
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
            """
            cursor = db.execute(
                query,
                (termino, patron_like, termino, termino, patron_prefix),
            )
            rows = cursor.fetchall()
            if not rows:
                return None

            # Procesar filas unificadas
            colonia_principal_id = None
            colonia_info = None
            sector_info = None
            programacion = []
            coincidencias_map = {}

            for row in rows:
                cid = row["id_colonia"]
                c_nom = row["nombre_colonia"]
                c_cp = row["codigo_postal"]
                c_zona = row["zona"]
                s_id = row["id_sector"]
                s_nom = row["nombre_sector"]
                s_desc = row["sector_descripcion"]

                if colonia_principal_id is None:
                    colonia_principal_id = cid
                    colonia_info = {
                        "id_colonia": cid,
                        "nombre": c_nom,
                        "nombre_colonia": c_nom,
                        "codigo_postal": c_cp,
                        "zona": c_zona or "Zona Metropolitana",
                        "id_sector": s_id,
                    }
                    sector_info = {
                        "id_sector": s_id,
                        "nombre": s_nom,
                        "nombre_sector": s_nom,
                        "descripcion": s_desc or f"Red de distribución sector {s_id}",
                        "red_hidraulica": s_desc or "Red General",
                        "disponibilidad": "Disponible",
                    }

                # Si corresponde a la colonia principal y tiene programación
                if cid == colonia_principal_id and row["id_programacion"] is not None:
                    programacion.append({
                        "id_programacion": row["id_programacion"],
                        "id_colonia": cid,
                        "dia_semana": row["dia_semana"],
                        "hora_inicio": row["hora_inicio"],
                        "hora_fin": row["hora_fin"],
                        "estado_servicio": row["estado_servicio"],
                        "fecha_actualizacion": row["fecha_actualizacion"],
                    })

                # Almacenar en coincidencias si es distinta
                if cid not in coincidencias_map:
                    coincidencias_map[cid] = {
                        "id_colonia": cid,
                        "nombre": c_nom,
                        "nombre_colonia": c_nom,
                        "codigo_postal": c_cp,
                        "zona": c_zona or "Zona Metropolitana",
                        "id_sector": s_id,
                        "nombre_sector": s_nom,
                    }

            coincidencias = list(coincidencias_map.values())[:limite]

            return {
                "colonia": colonia_info,
                "sector": sector_info,
                "programacion": programacion,
                "coincidencias": coincidencias,
            }

        # Fallback a tablas históricas (Colonia + Sector + ProgramacionTandeo)
        return self._consultar_historica(termino, limite)

    def _consultar_historica(self, termino: str, limite: int = 10) -> Optional[Dict[str, Any]]:
        """Consulta unificada para el esquema con nombres en PascalCase."""
        db = get_db()
        patron_like = f"%{termino}%"
        patron_prefix = f"{termino}%"

        query = """
            SELECT 
                c.id_colonia,
                c.nombre_colonia,
                c.codigo_postal,
                c.id_sector,
                s.nombre_sector,
                s.red_hidraulica,
                s.disponibilidad,
                pt.id_programacion,
                pt.dia_semana,
                pt.hora_inicio,
                pt.hora_fin,
                pt.estado_servicio,
                pt.fecha_actualizacion
            FROM Colonia c
            INNER JOIN Sector s ON c.id_sector = s.id_sector
            LEFT JOIN ProgramacionTandeo pt ON s.id_sector = pt.id_sector
            WHERE c.codigo_postal = ? OR c.nombre_colonia LIKE ?
            ORDER BY
                CASE
                    WHEN c.codigo_postal = ? THEN 1
                    WHEN LOWER(c.nombre_colonia) = LOWER(?) THEN 2
                    WHEN LOWER(c.nombre_colonia) LIKE LOWER(?) THEN 3
                    ELSE 4
                END,
                c.nombre_colonia ASC,
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
        """
        cursor = db.execute(
            query,
            (termino, patron_like, termino, termino, patron_prefix),
        )
        rows = cursor.fetchall()
        if not rows:
            return None

        colonia_principal_id = None
        colonia_info = None
        sector_info = None
        programacion = []
        coincidencias_map = {}

        for row in rows:
            cid = row["id_colonia"]
            c_nom = row["nombre_colonia"]
            c_cp = row["codigo_postal"]
            s_id = row["id_sector"]
            s_nom = row["nombre_sector"]

            if colonia_principal_id is None:
                colonia_principal_id = cid
                colonia_info = {
                    "id_colonia": cid,
                    "nombre": c_nom,
                    "nombre_colonia": c_nom,
                    "codigo_postal": c_cp,
                    "zona": "Zona Metropolitana",
                    "id_sector": s_id,
                }
                sector_info = {
                    "id_sector": s_id,
                    "nombre": s_nom,
                    "nombre_sector": s_nom,
                    "descripcion": row["red_hidraulica"],
                    "red_hidraulica": row["red_hidraulica"],
                    "disponibilidad": row["disponibilidad"],
                }

            if cid == colonia_principal_id and row["id_programacion"] is not None:
                programacion.append({
                    "id_programacion": row["id_programacion"],
                    "id_colonia": cid,
                    "dia_semana": row["dia_semana"],
                    "hora_inicio": row["hora_inicio"],
                    "hora_fin": row["hora_fin"],
                    "estado_servicio": row["estado_servicio"],
                    "fecha_actualizacion": row["fecha_actualizacion"],
                })

            if cid not in coincidencias_map:
                coincidencias_map[cid] = {
                    "id_colonia": cid,
                    "nombre": c_nom,
                    "nombre_colonia": c_nom,
                    "codigo_postal": c_cp,
                    "zona": "Zona Metropolitana",
                    "id_sector": s_id,
                    "nombre_sector": s_nom,
                }

        coincidencias = list(coincidencias_map.values())[:limite]

        return {
            "colonia": colonia_info,
            "sector": sector_info,
            "programacion": programacion,
            "coincidencias": coincidencias,
        }

    def buscar_colonias(self, termino: str, limite: int = 10) -> List[Dict[str, Any]]:
        """Busca colonias coincidentes por nombre o código postal de forma parametrizada."""
        termino = (termino or "").strip()
        if not termino:
            return []

        resultado_unificado = self.consultar_unificada(termino, limite=limite)
        if not resultado_unificado:
            return []

        return resultado_unificado.get("coincidencias", [])

    def obtener_sector_por_id(self, id_sector: int) -> Optional[Dict[str, Any]]:
        """Obtiene información de un sector por su ID usando consulta parametrizada."""
        db = get_db()
        # Verificar tabla sectores
        cur_check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sectores'"
        )
        if cur_check.fetchone():
            row = db.execute(
                "SELECT id_sector, nombre, descripcion FROM sectores WHERE id_sector = ? LIMIT 1",
                (id_sector,),
            ).fetchone()
            if row:
                return {
                    "id_sector": row["id_sector"],
                    "nombre": row["nombre"],
                    "nombre_sector": row["nombre"],
                    "descripcion": row["descripcion"],
                    "red_hidraulica": row["descripcion"],
                    "disponibilidad": "Disponible",
                }

        row = db.execute(
            "SELECT id_sector, nombre_sector, red_hidraulica, disponibilidad FROM Sector WHERE id_sector = ? LIMIT 1",
            (id_sector,),
        ).fetchone()

        if not row:
            return None

        return {
            "id_sector": row["id_sector"],
            "nombre": row["nombre_sector"],
            "nombre_sector": row["nombre_sector"],
            "descripcion": row["red_hidraulica"],
            "red_hidraulica": row["red_hidraulica"],
            "disponibilidad": row["disponibilidad"],
        }

    def obtener_programacion_por_sector(self, id_sector: int) -> List[Dict[str, Any]]:
        """Obtiene la programación semanal completa de un sector ordenada por día cronológico."""
        db = get_db()
        cursor = db.execute(
            """
            SELECT id_programacion, id_sector, dia_semana, hora_inicio, hora_fin,
                   estado_servicio, fecha_actualizacion
            FROM ProgramacionTandeo
            WHERE id_sector = ?
            ORDER BY
                CASE dia_semana
                    WHEN 'Lunes' THEN 1
                    WHEN 'Martes' THEN 2
                    WHEN 'Miércoles' THEN 3
                    WHEN 'Jueves' THEN 4
                    WHEN 'Viernes' THEN 5
                    WHEN 'Sábado' THEN 6
                    WHEN 'Domingo' THEN 7
                    ELSE 8
                END,
                hora_inicio ASC
            """,
            (id_sector,),
        )
        rows = cursor.fetchall()
        return [
            {
                "id_programacion": row["id_programacion"],
                "id_sector": row["id_sector"],
                "dia_semana": row["dia_semana"],
                "hora_inicio": row["hora_inicio"],
                "hora_fin": row["hora_fin"],
                "estado_servicio": row["estado_servicio"],
                "fecha_actualizacion": row["fecha_actualizacion"],
            }
            for row in rows
        ]
