from typing import Optional, Tuple
from werkzeug.security import check_password_hash, generate_password_hash

from app.models.usuario import Usuario
from app.repositories.usuario_repository import UsuarioRepository


class AuthService:
    """Lógica de autenticación, desacoplada de Flask y de SQLite."""

    def __init__(self, usuario_repo: UsuarioRepository) -> None:
        self._repo = usuario_repo

    def authenticate(self, correo: str, password: str) -> Tuple[Optional[Usuario], Optional[str]]:
        """
        Valida credenciales.

        Retorna (usuario, None) si son correctas.
        Retorna (None, motivo) si fallan; 'motivo' es un código interno
        que la ruta traduce a un mensaje genérico.
        """
        correo = (correo or "").strip().lower()
        if not correo or not password:
            return None, "credenciales_invalidas"

        usuario = self._repo.find_by_correo(correo)
        if usuario is None:
            # Ejecutamos un hash "señuelo" para mitigar timing attacks.
            check_password_hash(
                "pbkdf2:sha256:600000$dummy$"
                "0000000000000000000000000000000000000000000000000000000000000000",
                password,
            )
            return None, "credenciales_invalidas"

        if not check_password_hash(usuario.credenciales, password):
            return None, "credenciales_invalidas"

        if not usuario.activo:
            return None, "usuario_inactivo"

        return usuario, None

    def existe_correo(self, correo: str) -> bool:
        """Verifica si un correo electrónico ya se encuentra registrado."""
        return self._repo.existe_correo((correo or "").strip().lower())

    def registrar_usuario(
        self,
        nombre: str,
        correo: str,
        password: str,
        telefono: Optional[str] = None,
        rol: str = "Ciudadano",
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Valida que el correo no esté duplicado, cifra la contraseña de forma segura
        e inserta el nuevo usuario con rol predeterminado 'Ciudadano'.
        Retorna (exito, id_usuario, mensaje_error).
        """
        correo_limpio = (correo or "").strip().lower()
        if not correo_limpio or not password or not (nombre or "").strip():
            return False, None, "Nombre, correo y contraseña son obligatorios."

        if self._repo.find_by_correo(correo_limpio) is not None:
            return False, None, "El correo electrónico ya se encuentra registrado."

        credenciales_hash = generate_password_hash(password)
        id_usuario = self._repo.crear_usuario(
            nombre=nombre.strip(),
            correo=correo_limpio,
            credenciales=credenciales_hash,
            telefono=telefono,
            rol=rol,
            activo=1,
        )
        return True, id_usuario, None