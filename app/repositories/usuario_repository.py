from typing import Optional
from app.models.usuario import Usuario
from app.repositories.db import get_db


class UsuarioRepository:
    """Acceso a datos de Usuario. Solo consultas parametrizadas."""

    def _has_column(self, table: str, column: str) -> bool:
        db = get_db()
        columns = [
            row["name"]
            for row in db.execute(f"PRAGMA table_info({table})").fetchall()
        ]
        return column in columns

    def find_by_correo(self, correo: str) -> Optional[Usuario]:
        db = get_db()
        has_activo = self._has_column("Usuario", "activo")

        if has_activo:
            query = """
            SELECT id_usuario, nombre, telefono, correo,
                   notif_email, notif_sms, rol, credenciales, activo
            FROM Usuario
            WHERE correo = ?
            LIMIT 1
            """
        else:
            query = """
            SELECT id_usuario, nombre, telefono, correo,
                   notif_email, notif_sms, rol, credenciales
            FROM Usuario
            WHERE correo = ?
            LIMIT 1
            """

        row = db.execute(query, (correo,)).fetchone()

        if row is None:
            return None

        activo = bool(row["activo"]) if "activo" in row.keys() else True

        return Usuario(
            id_usuario=row["id_usuario"],
            nombre=row["nombre"],
            correo=row["correo"],
            rol=row["rol"],
            credenciales=row["credenciales"],
            activo=activo,
            telefono=row["telefono"],
            notif_email=bool(row["notif_email"]),
            notif_sms=bool(row["notif_sms"]),
        )

    def existe_correo(self, correo: str) -> bool:
        """Verifica si un correo electrónico ya se encuentra registrado."""
        return self.find_by_correo(correo) is not None

    def crear_usuario(
        self,
        nombre: str,
        correo: str,
        credenciales: str,
        telefono: Optional[str] = None,
        rol: str = "Ciudadano",
        activo: int = 1,
    ) -> int:
        """Inserta un nuevo usuario con consulta estrictamente parametrizada. Retorna el id_usuario."""
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO Usuario (nombre, correo, credenciales, telefono, rol, activo)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                nombre.strip(),
                correo.strip().lower(),
                credenciales,
                telefono.strip() if telefono else None,
                rol,
                activo,
            ),
        )
        db.commit()
        return cursor.lastrowid