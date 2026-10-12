import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "database", "tandeos.db")
ADMIN_EMAIL = "admin@cmas.gob.mx"
ADMIN_NOMBRE = "Administrador General"
ADMIN_ROL = "Administrador"
ADMIN_PASSWORD_RAW = "admin123"


def seed_admin() -> None:
    hash_credenciales = generate_password_hash(ADMIN_PASSWORD_RAW)

    conexion = sqlite3.connect(DB_PATH)
    try:
        cursor = conexion.cursor()

        # 1. Verificar existencia con consulta parametrizada
        cursor.execute(
            "SELECT id_usuario FROM Usuario WHERE correo = ? LIMIT 1",
            (ADMIN_EMAIL,),
        )
        row = cursor.fetchone()

        if row is None:
            # 2. Insertar nuevo administrador
            cursor.execute(
                """
                INSERT INTO Usuario (nombre, correo, rol, credenciales)
                VALUES (?, ?, ?, ?)
                """,
                (ADMIN_NOMBRE, ADMIN_EMAIL, ADMIN_ROL, hash_credenciales),
            )
        else:
            # 3. Actualizar únicamente credenciales
            cursor.execute(
                """
                UPDATE Usuario
                SET credenciales = ?
                WHERE correo = ?
                """,
                (hash_credenciales, ADMIN_EMAIL),
            )

        conexion.commit()
        print("SEED_EXITOSO")
    finally:
        conexion.close()


if __name__ == "__main__":
    seed_admin()
