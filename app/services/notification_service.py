"""
Servicio de Negocio para el Sistema de Notificaciones y Alertas de CMAS Xalapa.
Gestiona validación de preferencias, colas con estados controlados, regla automática
de recordatorios de corte a 24 horas y despacho mediante proveedores desacoplados.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.repositories.notification_repository import NotificationRepository
from app.services.providers.base_provider import BaseNotificationProvider
from app.services.providers.mock_provider import MockNotificationProvider

logger = logging.getLogger(__name__)

TIPOS_NOTIFICACION_VALIDOS = {
    "recordatorio_corte",
    "inicio_tandeo",
    "cambio_programacion",
    "suspension",
    "mantenimiento",
    "contingencia",
    "confirmacion_reporte",
}

CANALES_VALIDOS = {"email", "sms"}

DIAS_SEMANA_MAP = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}


class NotificationService:
    """Lógica central del subsistema de alertas y notificaciones."""

    def __init__(
        self,
        repo: Optional[NotificationRepository] = None,
        email_provider: Optional[BaseNotificationProvider] = None,
        sms_provider: Optional[BaseNotificationProvider] = None,
    ) -> None:
        self._repo = repo or NotificationRepository()
        self._email_provider = email_provider or MockNotificationProvider()
        self._sms_provider = sms_provider or MockNotificationProvider()

    # =========================================================================
    # 1. Gestión de Preferencias
    # =========================================================================

    def obtener_preferencias(self, id_usuario: int) -> Optional[Dict[str, Any]]:
        """Obtiene las preferencias de notificación de un usuario."""
        return self._repo.obtener_preferencias(id_usuario)

    def actualizar_preferencias(
        self,
        id_usuario: int,
        notif_email: bool,
        notif_sms: bool,
        id_colonia: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Actualiza las preferencias de canal y colonia preferida del usuario."""
        usuario = self._repo.obtener_usuario_por_id(id_usuario)
        if not usuario:
            raise ValueError(f"El usuario con ID {id_usuario} no existe.")

        return self._repo.guardar_preferencias(
            id_usuario=id_usuario,
            notif_email=bool(notif_email),
            notif_sms=bool(notif_sms),
            id_colonia=id_colonia,
        )

    # =========================================================================
    # 2. Creación y Encolado de Alertas
    # =========================================================================

    def crear_notificacion(
        self,
        id_usuario: int,
        tipo: str,
        canal: str,
        mensaje: str,
    ) -> Optional[int]:
        """
        Crea una notificación individual en la cola si el usuario tiene el canal habilitado.
        Si la preferencia del usuario para ese canal está inactiva, se omite silenciosamente.
        """
        if tipo not in TIPOS_NOTIFICACION_VALIDOS:
            raise ValueError(f"Tipo de notificación inválido: '{tipo}'.")
        if canal not in CANALES_VALIDOS:
            raise ValueError(f"Canal inválido: '{canal}'. Debe ser 'email' o 'sms'.")

        mensaje_limpio = (mensaje or "").strip()
        if not mensaje_limpio:
            raise ValueError("El mensaje de la notificación no puede estar vacío.")

        # Validar preferencias del usuario
        preferencias = self._repo.obtener_preferencias(id_usuario)
        if not preferencias:
            # Si no existe preferencia, no se puede verificar consentimiento
            return None

        canal_habilitado = (
            bool(preferencias.get("notif_email"))
            if canal == "email"
            else bool(preferencias.get("notif_sms"))
        )

        if not canal_habilitado:
            logger.info(
                "Canal '%s' desactivado por el usuario %d. Omitiendo notificación.",
                canal,
                id_usuario,
            )
            return None

        return self._repo.crear_notificacion(
            id_usuario=id_usuario,
            tipo=tipo,
            canal=canal,
            mensaje=mensaje_limpio,
            estado="Pendiente",
        )

    def crear_alerta(
        self,
        id_usuario: int,
        tipo: str,
        mensaje: str,
        canales: Optional[List[str]] = None,
    ) -> List[int]:
        """
        Genera alertas para un usuario evaluando sus preferencias activas.
        Si no se especifican canales, se encola para todos los canales que tenga habilitados.
        """
        if tipo not in TIPOS_NOTIFICACION_VALIDOS:
            raise ValueError(f"Tipo de notificación inválido: '{tipo}'.")

        preferencias = self._repo.obtener_preferencias(id_usuario)
        if not preferencias:
            return []

        canales_a_evaluar = canales or ["email", "sms"]
        ids_creados: List[int] = []

        for canal in canales_a_evaluar:
            if canal not in CANALES_VALIDOS:
                continue
            habilitado = (
                bool(preferencias.get("notif_email"))
                if canal == "email"
                else bool(preferencias.get("notif_sms"))
            )
            if habilitado:
                id_notif = self._repo.crear_notificacion(
                    id_usuario=id_usuario,
                    tipo=tipo,
                    canal=canal,
                    mensaje=mensaje.strip(),
                    estado="Pendiente",
                )
                ids_creados.append(id_notif)

        return ids_creados

    # =========================================================================
    # 3. Procesamiento y Despacho de la Cola (Gestión de Estados)
    # =========================================================================

    def procesar_notificacion(self, id_notificacion: int) -> Dict[str, Any]:
        """
        Procesa una notificación individual:
        Transición controlada: Pendiente -> Procesando -> (Enviado | Error).
        Captura excepciones registrando el motivo exacto del fallo.
        """
        notif = self._repo.obtener_notificacion_por_id(id_notificacion)
        if not notif:
            return {"exito": False, "error": "Notificación no encontrada"}

        if notif["estado"] not in ("Pendiente", "Error"):
            return {
                "exito": False,
                "mensaje": f"La notificación se encuentra en estado '{notif['estado']}'",
            }

        # 1. Transición a 'Procesando'
        self._repo.actualizar_estado(id_notificacion, "Procesando")

        canal = notif["canal"]
        provider = self._email_provider if canal == "email" else self._sms_provider
        destino = notif["correo"] if canal == "email" else notif["telefono"]

        # Validar destino disponible
        if not destino or not str(destino).strip():
            motivo = f"El usuario {notif['id_usuario']} no tiene {canal} registrado."
            self._repo.actualizar_estado(id_notificacion, "Error", motivo_error=motivo)
            return {"exito": False, "estado": "Error", "error": motivo}

        # 2. Intentar despacho mediante el proveedor correspondiente
        try:
            provider.enviar(
                destino=str(destino).strip(),
                mensaje=notif["mensaje"],
                tipo=notif["tipo"],
                id_notificacion=id_notificacion,
            )
            # 3. Transición a 'Enviado'
            self._repo.actualizar_estado(
                id_notificacion=id_notificacion,
                nuevo_estado="Enviado",
                fecha_envio=datetime.now(),
                motivo_error=None,
            )
            return {"exito": True, "estado": "Enviado", "destino": destino}
        except Exception as ex:
            # 4. Transición a 'Error' capturando motivo
            motivo_error = f"{type(ex).__name__}: {str(ex)}"
            logger.error(
                "Error despachando notificación %d via %s: %s",
                id_notificacion,
                canal,
                motivo_error,
            )
            self._repo.actualizar_estado(
                id_notificacion=id_notificacion,
                nuevo_estado="Error",
                motivo_error=motivo_error,
            )
            return {"exito": False, "estado": "Error", "error": motivo_error}

    def procesar_cola(self, limite: int = 50) -> Dict[str, Any]:
        """
        Procesa el lote pendiente de la cola de notificaciones.
        Retorna estadísticas completas del proceso.
        """
        pendientes = self._repo.obtener_pendientes(limite=limite)
        total = len(pendientes)
        enviadas = 0
        fallidas = 0
        detalles: List[Dict[str, Any]] = []

        for p in pendientes:
            res = self.procesar_notificacion(p["id_notificacion"])
            if res.get("exito"):
                enviadas += 1
            else:
                fallidas += 1
            detalles.append({"id_notificacion": p["id_notificacion"], **res})

        return {
            "total_procesadas": total,
            "enviadas": enviadas,
            "fallidas": fallidas,
            "detalles": detalles,
        }

    # =========================================================================
    # 4. Motor de Reglas Automáticas (Recordatorios 24h)
    # =========================================================================

    def evaluar_recordatorios_24h(
        self,
        fecha_referencia: Optional[datetime] = None,
        id_colonia: Optional[int] = None,
        id_usuario_especifico: Optional[int] = None,
    ) -> List[int]:
        """
        Cruza la programación semanal en 'programacion_tandeos' con la fecha/hora actual + 24h.
        Detecta cortes programados en exactamente 24 horas y genera alertas de recordatorio.
        Evita duplicados si la alerta ya fue encolada previamente.
        """
        ahora = fecha_referencia or datetime.now()
        objetivo_24h = ahora + timedelta(hours=24)

        dia_objetivo = DIAS_SEMANA_MAP.get(objetivo_24h.weekday(), "Lunes")
        hora_objetivo = objetivo_24h.strftime("%H:%M")

        # Buscar cortes programados para el día y hora objetivo
        cortes = self._repo.obtener_cortes_programados(
            dia_semana=dia_objetivo,
            hora_referencia=hora_objetivo,
            id_colonia=id_colonia,
        )

        if not cortes:
            return []

        ids_generados: List[int] = []

        for corte in cortes:
            col_id = corte["id_colonia"]
            col_nombre = corte["nombre_colonia"]
            hora_inicio = corte["hora_inicio"]

            mensaje_alerta = (
                f"Aviso CMAS: Se tiene programado corte de agua en la colonia {col_nombre} "
                f"para el día {dia_objetivo} a partir de las {hora_inicio} hrs. "
                "Tome sus debidas previsiones y almacene agua con anticipación."
            )

            # Destinatarios: usuarios suscritos a esta colonia
            if id_usuario_especifico is not None:
                usr = self._repo.obtener_usuario_por_id(id_usuario_especifico)
                destinatarios = [usr] if usr else []
            else:
                destinatarios = self._repo.obtener_usuarios_para_colonia(col_id)
                # Si no hay usuarios explícitamente suscritos a la colonia, buscar usuarios con colonia coincidente
                if not destinatarios:
                    todos = self._repo.obtener_todos_usuarios_activos()
                    destinatarios = [u for u in todos if u.get("id_colonia") == col_id]

            for dest in destinatarios:
                id_usr = dest["id_usuario"]
                # Anti-spam: Evitar duplicar alertas idénticas dentro de la misma ventana de 20 horas
                if self._repo.existe_notificacion_reciente(
                    id_usr, "recordatorio_corte", mensaje_alerta, horas=20
                ):
                    continue

                creados = self.crear_alerta(
                    id_usuario=id_usr,
                    tipo="recordatorio_corte",
                    mensaje=mensaje_alerta,
                )
                ids_generados.extend(creados)

        return ids_generados

    # =========================================================================
    # 5. Consultas de Historial y Auditoría
    # =========================================================================

    def obtener_historial_usuario(
        self,
        id_usuario: int,
        canal: Optional[str] = None,
        estado: Optional[str] = None,
        tipo: Optional[str] = None,
        limite: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Consulta el historial de notificaciones de un usuario particular."""
        return self._repo.obtener_historial(
            id_usuario=id_usuario,
            canal=canal,
            estado=estado,
            tipo=tipo,
            limite=limite,
            offset=offset,
        )

    def obtener_auditoria_notificacion(self, id_notificacion: int) -> List[Dict[str, Any]]:
        """Obtiene la bitácora histórica completa de transiciones de una notificación."""
        return self._repo.obtener_bitacora(id_notificacion)
