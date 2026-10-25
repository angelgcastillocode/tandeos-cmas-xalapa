"""
Repositorio de Notificaciones y Preferencias de Usuario para CMAS Xalapa.
Consultas 100% parametrizadas con placeholders '?' contra database/tandeos.db.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from app.repositories.db import get_db


class NotificationRepository:
    """Acceso a datos de notificaciones, colas, preferencias y bitácora de auditoría."""

    # =========================================================================
    # 1. Preferencias de Notificación
    # =========================================================================

    def obtener_preferencias(self, id_usuario: int) -> Optional[Dict[str, Any]]:
        """Obtiene las preferencias de un usuario específico."""
        db = get_db()
        sql = """
            SELECT up.id_preferencia, up.id_usuario, up.notif_email, up.notif_sms,
                   up.id_colonia, up.fecha_actualizacion,
                   c.nombre AS nombre_colonia
            FROM usuario_preferencias up
            LEFT JOIN colonias c ON up.id_colonia = c.id_colonia
            WHERE up.id_usuario = ?
            LIMIT 1
        """
        row = db.execute(sql, (id_usuario,)).fetchone()
        if not row:
            # Si no existe registro aún en usuario_preferencias, sincronizar desde Usuario
            usr = self.obtener_usuario_por_id(id_usuario)
            if not usr:
                return None
            return self.guardar_preferencias(
                id_usuario=id_usuario,
                notif_email=bool(usr.get("notif_email", 1)),
                notif_sms=bool(usr.get("notif_sms", 0)),
                id_colonia=None,
            )
        return dict(row)

    def guardar_preferencias(
        self,
        id_usuario: int,
        notif_email: bool,
        notif_sms: bool,
        id_colonia: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Crea o actualiza las preferencias de notificación de un usuario."""
        db = get_db()
        sql = """
            INSERT INTO usuario_preferencias (id_usuario, notif_email, notif_sms, id_colonia, fecha_actualizacion)
            VALUES (?, ?, ?, ?, DATETIME('now', 'localtime'))
            ON CONFLICT(id_usuario) DO UPDATE SET
                notif_email = excluded.notif_email,
                notif_sms = excluded.notif_sms,
                id_colonia = excluded.id_colonia,
                fecha_actualizacion = DATETIME('now', 'localtime')
        """
        db.execute(sql, (id_usuario, int(notif_email), int(notif_sms), id_colonia))

        # Sincronizar en tabla Usuario si contiene las columnas
        try:
            db.execute(
                "UPDATE Usuario SET notif_email = ?, notif_sms = ? WHERE id_usuario = ?",
                (int(notif_email), int(notif_sms), id_usuario),
            )
        except Exception:
            pass

        db.commit()
        pref = self.obtener_preferencias(id_usuario)
        return pref or {}

    # =========================================================================
    # 2. Cola de Notificaciones e Historial
    # =========================================================================

    def crear_notificacion(
        self,
        id_usuario: int,
        tipo: str,
        canal: str,
        mensaje: str,
        estado: str = "Pendiente",
    ) -> int:
        """Inserta una nueva notificación en la cola/historial con estado inicial."""
        db = get_db()
        sql = """
            INSERT INTO notificaciones_historial (
                id_usuario, tipo, canal, mensaje, estado, fecha_generacion
            )
            VALUES (?, ?, ?, ?, ?, DATETIME('now', 'localtime'))
        """
        cur = db.execute(sql, (id_usuario, tipo, canal, mensaje, estado))
        db.commit()
        id_notif = cur.lastrowid

        # Registrar bitácora de auditoría histórica
        self.registrar_bitacora(
            id_notificacion=id_notif,
            estado_anterior=None,
            estado_nuevo=estado,
            detalle="Notificación encolada",
        )
        return id_notif

    def obtener_notificacion_por_id(self, id_notificacion: int) -> Optional[Dict[str, Any]]:
        """Busca una notificación por su identificador primario."""
        db = get_db()
        sql = """
            SELECT nh.id_notificacion, nh.id_usuario, nh.tipo, nh.canal, nh.mensaje,
                   nh.estado, nh.fecha_generacion, nh.fecha_envio, nh.motivo_error,
                   u.nombre AS nombre_usuario, u.correo, u.telefono
            FROM notificaciones_historial nh
            JOIN Usuario u ON nh.id_usuario = u.id_usuario
            WHERE nh.id_notificacion = ?
            LIMIT 1
        """
        row = db.execute(sql, (id_notificacion,)).fetchone()
        return dict(row) if row else None

    def obtener_pendientes(self, limite: int = 50) -> List[Dict[str, Any]]:
        """Obtiene un lote de notificaciones en estado 'Pendiente' listas para procesar."""
        db = get_db()
        sql = """
            SELECT nh.id_notificacion, nh.id_usuario, nh.tipo, nh.canal, nh.mensaje,
                   nh.estado, nh.fecha_generacion,
                   u.nombre AS nombre_usuario, u.correo, u.telefono
            FROM notificaciones_historial nh
            JOIN Usuario u ON nh.id_usuario = u.id_usuario
            WHERE nh.estado = 'Pendiente'
            ORDER BY nh.fecha_generacion ASC
            LIMIT ?
        """
        rows = db.execute(sql, (limite,)).fetchall()
        return [dict(r) for r in rows]

    def actualizar_estado(
        self,
        id_notificacion: int,
        nuevo_estado: str,
        motivo_error: Optional[str] = None,
        fecha_envio: Optional[datetime] = None,
    ) -> bool:
        """Actualiza el estado de la notificación y registra la transición en bitácora."""
        db = get_db()
        # Obtener estado previo para auditoría
        prev = db.execute(
            "SELECT estado FROM notificaciones_historial WHERE id_notificacion = ?",
            (id_notificacion,),
        ).fetchone()
        if not prev:
            return False

        estado_anterior = prev["estado"]
        str_fecha_envio = (
            fecha_envio.strftime("%Y-%m-%d %H:%M:%S")
            if fecha_envio
            else (datetime.now().strftime("%Y-%m-%d %H:%M:%S") if nuevo_estado == "Enviado" else None)
        )

        sql = """
            UPDATE notificaciones_historial
            SET estado = ?,
                motivo_error = ?,
                fecha_envio = ?
            WHERE id_notificacion = ?
        """
        db.execute(sql, (nuevo_estado, motivo_error, str_fecha_envio, id_notificacion))
        db.commit()

        # Auditoría histórica del cambio de estado
        detalle = f"Transición de estado: {estado_anterior} -> {nuevo_estado}"
        if motivo_error:
            detalle += f" | Error: {motivo_error}"
        self.registrar_bitacora(id_notificacion, estado_anterior, nuevo_estado, detalle)
        return True

    def registrar_bitacora(
        self,
        id_notificacion: int,
        estado_anterior: Optional[str],
        estado_nuevo: str,
        detalle: Optional[str] = None,
    ) -> int:
        """Registra un evento en la bitácora de auditoría histórica."""
        db = get_db()
        sql = """
            INSERT INTO notificaciones_bitacora (
                id_notificacion, estado_anterior, estado_nuevo, detalle, fecha_cambio
            )
            VALUES (?, ?, ?, ?, DATETIME('now', 'localtime'))
        """
        cur = db.execute(sql, (id_notificacion, estado_anterior, estado_nuevo, detalle))
        db.commit()
        return cur.lastrowid

    def obtener_historial(
        self,
        id_usuario: Optional[int] = None,
        canal: Optional[str] = None,
        estado: Optional[str] = None,
        tipo: Optional[str] = None,
        limite: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Consulta histórica filtrada y paginada de notificaciones con parámetros '?'."""
        db = get_db()
        sql = """
            SELECT nh.id_notificacion, nh.id_usuario, nh.tipo, nh.canal, nh.mensaje,
                   nh.estado, nh.fecha_generacion, nh.fecha_envio, nh.motivo_error,
                   u.nombre AS nombre_usuario, u.correo
            FROM notificaciones_historial nh
            JOIN Usuario u ON nh.id_usuario = u.id_usuario
            WHERE 1=1
        """
        params: List[Any] = []
        if id_usuario is not None:
            sql += " AND nh.id_usuario = ?"
            params.append(id_usuario)
        if canal:
            sql += " AND nh.canal = ?"
            params.append(canal)
        if estado:
            sql += " AND nh.estado = ?"
            params.append(estado)
        if tipo:
            sql += " AND nh.tipo = ?"
            params.append(tipo)

        sql += " ORDER BY nh.fecha_generacion DESC LIMIT ? OFFSET ?"
        params.extend([limite, offset])

        rows = db.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def obtener_bitacora(self, id_notificacion: int) -> List[Dict[str, Any]]:
        """Obtiene la bitácora de auditoría histórica completa de una notificación."""
        db = get_db()
        sql = """
            SELECT id_bitacora, id_notificacion, estado_anterior, estado_nuevo,
                   detalle, fecha_cambio
            FROM notificaciones_bitacora
            WHERE id_notificacion = ?
            ORDER BY fecha_cambio ASC, id_bitacora ASC
        """
        rows = db.execute(sql, (id_notificacion,)).fetchall()
        return [dict(r) for r in rows]

    # =========================================================================
    # 3. Consultas para Regla 24h y Destinatarios
    # =========================================================================

    def obtener_usuario_por_id(self, id_usuario: int) -> Optional[Dict[str, Any]]:
        """Obtiene los datos base de un usuario por id."""
        db = get_db()
        sql = """
            SELECT id_usuario, nombre, correo, telefono, rol, activo,
                   notif_email, notif_sms
            FROM Usuario
            WHERE id_usuario = ?
            LIMIT 1
        """
        row = db.execute(sql, (id_usuario,)).fetchone()
        return dict(row) if row else None

    def obtener_usuarios_para_colonia(self, id_colonia: int) -> List[Dict[str, Any]]:
        """
        Obtiene usuarios asociados a una colonia específica en sus preferencias
        o activos que tengan preferencias configuradas.
        """
        db = get_db()
        sql = """
            SELECT u.id_usuario, u.nombre, u.correo, u.telefono,
                   up.notif_email, up.notif_sms, up.id_colonia
            FROM Usuario u
            JOIN usuario_preferencias up ON u.id_usuario = up.id_usuario
            WHERE up.id_colonia = ?
              AND u.activo = 1
              AND (up.notif_email = 1 OR up.notif_sms = 1)
        """
        rows = db.execute(sql, (id_colonia,)).fetchall()
        return [dict(r) for r in rows]

    def obtener_todos_usuarios_activos(self) -> List[Dict[str, Any]]:
        """Obtiene todos los usuarios activos con sus preferencias de notificación."""
        db = get_db()
        sql = """
            SELECT u.id_usuario, u.nombre, u.correo, u.telefono,
                   COALESCE(up.notif_email, u.notif_email, 1) AS notif_email,
                   COALESCE(up.notif_sms, u.notif_sms, 0) AS notif_sms,
                   up.id_colonia
            FROM Usuario u
            LEFT JOIN usuario_preferencias up ON u.id_usuario = up.id_usuario
            WHERE u.activo = 1
        """
        rows = db.execute(sql).fetchall()
        return [dict(r) for r in rows]

    def obtener_cortes_programados(
        self,
        dia_semana: str,
        hora_referencia: Optional[str] = None,
        id_colonia: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Consulta la programación semanal en 'programacion_tandeos' para detectar
        cortes (estados 'Suspendido' o 'Mantenimiento') en el día y horario solicitado.
        """
        db = get_db()
        sql = """
            SELECT pt.id_programacion, pt.id_colonia, pt.dia_semana,
                   pt.hora_inicio, pt.hora_fin, pt.estado_servicio,
                   c.nombre AS nombre_colonia, c.codigo_postal,
                   s.nombre AS nombre_sector
            FROM programacion_tandeos pt
            JOIN colonias c ON pt.id_colonia = c.id_colonia
            LEFT JOIN sectores s ON c.id_sector = s.id_sector
            WHERE pt.dia_semana = ?
              AND pt.estado_servicio IN ('Suspendido', 'Mantenimiento')
        """
        params: List[Any] = [dia_semana]
        if id_colonia is not None:
            sql += " AND pt.id_colonia = ?"
            params.append(id_colonia)

        if hora_referencia is not None:
            # Coincidencia con inicio del corte o dentro de la ventana de suspensión
            sql += " AND (pt.hora_inicio = ? OR (pt.hora_inicio <= ? AND pt.hora_fin >= ?))"
            params.extend([hora_referencia, hora_referencia, hora_referencia])

        sql += " ORDER BY c.nombre ASC"
        rows = db.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def existe_notificacion_reciente(
        self,
        id_usuario: int,
        tipo: str,
        mensaje: str,
        horas: int = 24,
    ) -> bool:
        """Verifica si ya se generó una notificación idéntica en las últimas N horas para evitar spam."""
        db = get_db()
        sql = """
            SELECT id_notificacion
            FROM notificaciones_historial
            WHERE id_usuario = ?
              AND tipo = ?
              AND mensaje = ?
              AND fecha_generacion >= DATETIME('now', 'localtime', ?)
            LIMIT 1
        """
        param_horas = f"-{horas} hours"
        row = db.execute(sql, (id_usuario, tipo, mensaje, param_horas)).fetchone()
        return row is not None
