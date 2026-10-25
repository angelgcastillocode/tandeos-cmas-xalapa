"""
Interfaz base para proveedores de mensajería y correo (Patrón Adaptador / Proveedor).
Desacopla el núcleo de CMAS Xalapa de servicios específicos (SendGrid, Twilio, AWS SES, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseNotificationProvider(ABC):
    """
    Contrato base que cualquier proveedor de mensajería debe satisfacer.
    """

    @abstractmethod
    def enviar(self, destino: str, mensaje: str, **kwargs: Any) -> bool:
        """
        Envía una notificación al destino indicado (correo electrónico o número telefónico).

        :param destino: Dirección de correo o número telefónico del receptor.
        :param mensaje: Contenido del mensaje de la alerta.
        :param kwargs: Parámetros opcionales adicionales (asunto, tipo, metadatos).
        :return: True si la transmisión fue aceptada por el proveedor.
        :raises Exception: Si ocurre una falla en el transporte, autenticación o rechazo.
        """
        pass
