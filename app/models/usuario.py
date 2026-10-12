from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Usuario:
    """Representación de un usuario autenticable."""
    id_usuario: int
    nombre: str
    correo: str
    rol: str
    credenciales: str           # hash PBKDF2-SHA256
    activo: bool = True
    telefono: Optional[str] = None
    notif_email: bool = False
    notif_sms: bool = False

    @property
    def es_administrativo(self) -> bool:
        return self.rol in ("Operador", "Administrador", "Supervisor")