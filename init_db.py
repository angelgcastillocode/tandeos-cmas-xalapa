import sqlite3
import os

# Ruta a tu base de datos SQLite
db_path = os.path.join("database", "tandeos.db")

# Asegurar que la carpeta database exista
os.makedirs("database", exist_ok=True)

# Conectar y crear las tablas necesarias (ej. tabla user)
conexion = sqlite3.connect(db_path)
cursor = conexion.cursor()

# Ejemplo de creación de la tabla user si maneja correo y password
cursor.execute("""
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    correo TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1
)
""")

conexion.commit()
conexion.close()

print("¡Base de datos y tablas inicializadas correctamente!")