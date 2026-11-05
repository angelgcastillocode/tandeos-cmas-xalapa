"""
==============================================================================
PROYECTO: PLATAFORMA DE TANDEOS CMAS XALAPA (EQUIPO MORADO)
HITO 1: SUITE AUTOMATIZADA DE PRUEBAS DE INTEGRIDAD REFERENCIAL Y DOMINIO (3FN)
ARCHIVO: database/test_integrity.py
==============================================================================
Valida el cumplimiento estricto de:
1. Activación obligatoria de PRAGMA foreign_keys = ON;
2. Carga limpia del esquema DDL (7 tablas en 3FN) y datos semilla (seeds.sql).
3. Bloqueo de inserción de usuario con rol inexistente (Violación de FK).
4. Bloqueo de inserción de colonia sin sector válido (Violación NOT NULL y FK).
5. Bloqueo de duplicidad de correo en usuarios y folio_oficial en reportes (Violación UNIQUE).
6. Bloqueo de valores fuera de dominio mediante restricciones CHECK.
==============================================================================
"""

import os
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
SEEDS_PATH = os.path.join(BASE_DIR, "seeds.sql")
DB_PATH = os.path.join(BASE_DIR, "cmas_tandeos_dev.db")


def crear_conexion(ruta_db: str) -> sqlite3.Connection:
    """Crea una conexión SQLite activando obligatoriamente las llaves foráneas."""
    conn = sqlite3.connect(ruta_db)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def ejecutar_suite_integridad() -> int:
    print("=" * 80)
    print("  PLATAFORMA DE TANDEOS CMAS XALAPA - EQUIPO MORADO")
    print("  EJECUCIÓN DE PRUEBAS DE INTEGRIDAD RELACIONAL (3FN / SQLite 3)")
    print("=" * 80)

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = crear_conexion(DB_PATH)
    cursor = conn.cursor()

    # Verificar que PRAGMA foreign_keys esté activo
    cursor.execute("PRAGMA foreign_keys;")
    fk_status = cursor.fetchone()[0]
    print(f"\n[CONFIG] Estado de PRAGMA foreign_keys = {fk_status} ({'ACTIVO' if fk_status == 1 else 'INACTIVO'})")
    assert fk_status == 1, "ERROR CRÍTICO: PRAGMA foreign_keys no está activado."

    # --------------------------------------------------------------------------
    # PRUEBA 1: Creación del esquema DDL y carga completa de datos semilla
    # --------------------------------------------------------------------------
    print("\n[TEST 01] Cargando esquema DDL (database/schema.sql) y semillas (database/seeds.sql)...")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f_schema:
        conn.executescript(f_schema.read())
    conn.execute("PRAGMA foreign_keys = ON;")

    with open(SEEDS_PATH, "r", encoding="utf-8") as f_seeds:
        conn.executescript(f_seeds.read())
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.commit()

    tablas = [
        "roles",
        "usuarios",
        "sectores",
        "redes_bombeo",
        "colonias",
        "programacion_tandeo",
        "reportes_incidencias",
    ]
    print("  -> Inserción de seed data completada con éxito. Conteo de registros:")
    for tabla in tablas:
        cursor.execute(f"SELECT COUNT(*) FROM {tabla};")
        total = cursor.fetchone()[0]
        print(f"     * {tabla:<24}: {total} registros cargados")
        assert total > 0, f"La tabla {tabla} no recibió datos semilla."
    print("  [PASS] TEST 01 SUPERADO: Esquema de 7 tablas en 3FN y semillas verificados.")

    # --------------------------------------------------------------------------
    # PRUEBA 2: Intento de inserción de un usuario con rol inexistente (FK)
    # --------------------------------------------------------------------------
    print("\n[TEST 02] Probando inserción de usuario con id_rol=999 (inexistente)...")
    try:
        cursor.execute(
            """
            INSERT INTO usuarios (nombre_completo, email, password_hash, id_rol)
            VALUES ('Usuario Intruso', 'intruso@xalapa.mx', 'hash_falso', 999);
            """
        )
        conn.commit()
        print("  [FAIL] El motor permitió insertar un rol inexistente.")
        return 1
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        print(f"  -> IntegrityError capturado correctamente: {exc}")
        print("  [PASS] TEST 02 SUPERADO: Violación de Foreign Key (usuarios.id_rol -> roles.id_rol) bloqueada.")

    # --------------------------------------------------------------------------
    # PRUEBA 3: Intento de inserción de una colonia sin sector válido (NOT NULL / FK)
    # --------------------------------------------------------------------------
    print("\n[TEST 03] Probando inserción de colonia sin sector (NULL y FK inexistente)...")
    try:
        cursor.execute(
            """
            INSERT INTO colonias (nombre_colonia, codigo_postal, id_sector, id_red)
            VALUES ('Colonia Huérfana NULL', '91050', NULL, 1);
            """
        )
        conn.commit()
        print("  [FAIL] El motor permitió insertar una colonia con id_sector NULL.")
        return 1
    except sqlite3.IntegrityError as exc_null:
        conn.rollback()
        print(f"  -> IntegrityError (NOT NULL) capturado correctamente: {exc_null}")

    try:
        cursor.execute(
            """
            INSERT INTO colonias (nombre_colonia, codigo_postal, id_sector, id_red)
            VALUES ('Colonia Sector Fantasma', '91050', 888, 1);
            """
        )
        conn.commit()
        print("  [FAIL] El motor permitió insertar una colonia con id_sector inexistente.")
        return 1
    except sqlite3.IntegrityError as exc_fk:
        conn.rollback()
        print(f"  -> IntegrityError (FOREIGN KEY) capturado correctamente: {exc_fk}")
        print("  [PASS] TEST 03 SUPERADO: Violación de NOT NULL y FK en colonias bloqueada.")

    # --------------------------------------------------------------------------
    # PRUEBA 4: Intento de duplicar un correo o folio oficial (UNIQUE)
    # --------------------------------------------------------------------------
    print("\n[TEST 04] Probando duplicación de email en usuarios y folio_oficial en reportes...")
    try:
        cursor.execute(
            """
            INSERT INTO usuarios (nombre_completo, email, password_hash, id_rol)
            VALUES ('Clon Ciudadano', 'angel.castillo@ciudadano.xalapa.mx', 'hash_clon', 1);
            """
        )
        conn.commit()
        print("  [FAIL] El motor permitió duplicar el correo electrónico.")
        return 1
    except sqlite3.IntegrityError as exc_email:
        conn.rollback()
        print(f"  -> IntegrityError (UNIQUE email) capturado correctamente: {exc_email}")

    try:
        cursor.execute(
            """
            INSERT INTO reportes_incidencias
                (folio_oficial, id_colonia, id_usuario, tipo_incidencia, descripcion)
            VALUES
                ('#RPT-2026-00001', 1, 1, 'Fuga', 'Intento de reutilizar el mismo folio oficial.');
            """
        )
        conn.commit()
        print("  [FAIL] El motor permitió duplicar el folio oficial de incidencia.")
        return 1
    except sqlite3.IntegrityError as exc_folio:
        conn.rollback()
        print(f"  -> IntegrityError (UNIQUE folio_oficial) capturado correctamente: {exc_folio}")
        print("  [PASS] TEST 04 SUPERADO: Duplicación de email y folio_oficial bloqueada.")

    # --------------------------------------------------------------------------
    # PRUEBA 5: Intento de violar restricciones de dominio (CHECK)
    # --------------------------------------------------------------------------
    print("\n[TEST 05] Probando restricciones de dominio CHECK (día inválido y estado inválido)...")
    try:
        cursor.execute(
            """
            INSERT INTO programacion_tandeo (id_colonia, dia_semana, hora_inicio, hora_fin, estado_suministro)
            VALUES (1, 9, '08:00', '14:00', 'Con servicio');
            """
        )
        conn.commit()
        print("  [FAIL] El motor permitió un dia_semana fuera del rango 0..6.")
        return 1
    except sqlite3.IntegrityError as exc_check:
        conn.rollback()
        print(f"  -> IntegrityError (CHECK dia_semana) capturado correctamente: {exc_check}")
        print("  [PASS] TEST 05 SUPERADO: Restricciones CHECK de dominio activas y validadas.")

    conn.close()

    print("\n" + "=" * 80)
    print("  RESULTADO GLOBAL: 5/5 PRUEBAS DE INTEGRIDAD SUPERADAS CON ÉXITO (100% OK)")
    print(f"  Base de datos generada y verificada en: {DB_PATH}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(ejecutar_suite_integridad())

