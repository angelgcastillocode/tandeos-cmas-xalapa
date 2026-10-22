from typing import Any, Dict, List, Optional
from app.models.reporte import ReporteCiudadano
from app.repositories.db import get_db


class ReporteRepository:
    """Acceso a datos para el registro y consulta de Reportes Ciudadanos (CU-002).
    Todas las consultas son estrictamente parametrizadas con placeholders (?).
    """

    def crear_reporte(self, reporte: ReporteCiudadano) -> int:
        """Inserta un nuevo reporte ciudadano de forma parametrizada. Retorna el ID generado."""
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO reportes_ciudadanos (
                folio, id_colonia, tipo_incidencia, descripcion,
                nombre_ciudadano, telefono_contacto, estado, id_usuario
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reporte.folio,
                reporte.id_colonia,
                reporte.tipo_incidencia,
                reporte.descripcion,
                reporte.nombre_ciudadano,
                reporte.telefono_contacto,
                reporte.estado or "Abierto",
                reporte.id_usuario,
            ),
        )
        db.commit()
        return cursor.lastrowid

    def obtener_por_folio(self, folio: str) -> Optional[Dict[str, Any]]:
        """Recupera un reporte por su folio único junto con el nombre de la colonia."""
        db = get_db()
        folio_limpio = (folio or "").strip().upper()

        # Verificar si existe tabla 'colonias' o fallback a 'Colonia'
        cur_check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='colonias'"
        )
        usa_colonias_nuevas = cur_check.fetchone() is not None

        if usa_colonias_nuevas:
            row = db.execute(
                """
                SELECT 
                    rc.id_reporte,
                    rc.folio,
                    rc.id_colonia,
                    rc.tipo_incidencia,
                    rc.descripcion,
                    rc.nombre_ciudadano,
                    rc.telefono_contacto,
                    rc.id_usuario,
                    rc.fecha_hora_reporte,
                    rc.estado,
                    c.nombre AS nombre_colonia,
                    c.codigo_postal
                FROM reportes_ciudadanos rc
                LEFT JOIN colonias c ON rc.id_colonia = c.id_colonia
                WHERE UPPER(rc.folio) = ?
                LIMIT 1
                """,
                (folio_limpio,),
            ).fetchone()
        else:
            row = db.execute(
                """
                SELECT 
                    rc.id_reporte,
                    rc.folio,
                    rc.id_colonia,
                    rc.tipo_incidencia,
                    rc.descripcion,
                    rc.nombre_ciudadano,
                    rc.telefono_contacto,
                    rc.id_usuario,
                    rc.fecha_hora_reporte,
                    rc.estado,
                    c.nombre_colonia,
                    c.codigo_postal
                FROM reportes_ciudadanos rc
                LEFT JOIN Colonia c ON rc.id_colonia = c.id_colonia
                WHERE UPPER(rc.folio) = ?
                LIMIT 1
                """,
                (folio_limpio,),
            ).fetchone()

        if not row:
            return None

        return {
            "id_reporte": row["id_reporte"],
            "folio": row["folio"],
            "id_colonia": row["id_colonia"],
            "tipo_incidencia": row["tipo_incidencia"],
            "descripcion": row["descripcion"],
            "nombre_ciudadano": row["nombre_ciudadano"] or "Anónimo",
            "telefono_contacto": row["telefono_contacto"] or "No proporcionado",
            "id_usuario": row["id_usuario"],
            "fecha_hora_reporte": row["fecha_hora_reporte"],
            "estado": row["estado"],
            "nombre_colonia": row["nombre_colonia"] or "Colonia no especificada",
            "codigo_postal": row["codigo_postal"] or "",
        }

    def existe_folio(self, folio: str) -> bool:
        """Comprueba si un folio ya se encuentra registrado para evitar colisiones."""
        db = get_db()
        row = db.execute(
            "SELECT 1 FROM reportes_ciudadanos WHERE folio = ? LIMIT 1",
            (folio,),
        ).fetchone()
        return row is not None

    def colonia_existe(self, id_colonia: int) -> bool:
        """Verifica que el ID de la colonia exista en la base de datos."""
        db = get_db()
        cur_check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='colonias'"
        )
        tabla = "colonias" if cur_check.fetchone() is not None else "Colonia"

        row = db.execute(
            f"SELECT 1 FROM {tabla} WHERE id_colonia = ? LIMIT 1",
            (id_colonia,),
        ).fetchone()
        return row is not None

    def listar_colonias(self) -> List[Dict[str, Any]]:
        """Lista todas las colonias disponibles para el selector del formulario."""
        db = get_db()
        cur_check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='colonias'"
        )
        if cur_check.fetchone() is not None:
            rows = db.execute(
                "SELECT id_colonia, nombre, codigo_postal FROM colonias ORDER BY nombre ASC"
            ).fetchall()
            return [
                {
                    "id_colonia": r["id_colonia"],
                    "nombre": r["nombre"],
                    "codigo_postal": r["codigo_postal"],
                }
                for r in rows
            ]
        else:
            rows = db.execute(
                "SELECT id_colonia, nombre_colonia AS nombre, codigo_postal FROM Colonia ORDER BY nombre_colonia ASC"
            ).fetchall()
            return [
                {
                    "id_colonia": r["id_colonia"],
                    "nombre": r["nombre"],
                    "codigo_postal": r["codigo_postal"],
                }
                for r in rows
            ]
