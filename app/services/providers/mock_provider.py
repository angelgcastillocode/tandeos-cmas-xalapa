"""
Implementación de prueba de un proveedor simulado (Mock) para desarrollo y testing.
Almacena mensajes en memoria y permite inducir fallos controlados para probar transiciones de estado.
"""

import logging
from typing import Any, Dict, List
from app.services.providers.base_provider import BaseNotificationProvider

logger = logging.getLogger(__name__)


class MockNotificationProvider(BaseNotificationProvider):
    """
    Proveedor simulado para entornos de prueba y desarrollo local sin dependencias externas.
    """

    def __init__(self, simular_fallo: bool = False, mensaje_error: str = "Error de red simulado en proveedor externo") -> None:
        self.simular_fallo = simular_fallo
        self.mensaje_error = mensaje_error
        self._envios: List[Dict[str, Any]] = []

    def enviar(self, destino: str, mensaje: str, **kwargs: Any) -> bool:
        """
        Registra el envío en memoria o eleva excepción si simular_fallo es True.
        """
        if self.simular_fallo:
            logger.warning("MockNotificationProvider: Error inducido enviando a %s", destino)
            raise RuntimeError(self.mensaje_error)

        registro = {
            "destino": destino,
            "mensaje": mensaje,
            "opciones": kwargs,
        }
        self._envios.append(registro)
        logger.info("MockNotificationProvider: Envío simulado a %s (%d chars)", destino, len(mensaje))
        return True

    @property
    def envios(self) -> List[Dict[str, Any]]:
        """Devuelve una copia del historial de envíos realizados."""
        return list(self._envios)

    def limpiar(self) -> None:
        """Limpia el buffer de envíos en memoria."""
        self._envios.clear()
