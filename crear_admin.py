import sqlite3
import os
from werkzeug.security import generate_password_hash

# Ruta a la base de datos
db_path = os.path.join("database", "tandeos.db")

# Contraseña en texto plano que escribirás en el formulario
password_plana = "123456"

# Generar el hash de seguridad (esto es lo que verifica tu app)
password_hasheada = generate_password_hash(password_plana)

# Conectar a SQLite
conexion = sqlite3.connect(db_path)
cursor = conexion.cursor()

# 1. Borrar el usuario anterior si es que existe (para evitar duplicados o errores de texto plano)
cursor.execute("DELETE FROM Usuario WHERE correo = 'admin@cmas.gob.mx'")

# 2. Insertar el usuario con la contraseña correctamente cifrada
cursor.execute("""
INSERT INTO Usuario (nombre, correo, rol, credenciales) 
VALUES ('Administrador', 'admin@cmas.gob.mx', 'Administrador', ?)
""", (password_hasheada,))

# Guardar los cambios y cerrar
conexion.commit()
conexion.close()

print(f"¡Usuario admin@cmas.gob.mx configurado con éxito!")
print(f"La contraseña '{password_plana}' ha sido cifrada y guardada en la base de datos.")