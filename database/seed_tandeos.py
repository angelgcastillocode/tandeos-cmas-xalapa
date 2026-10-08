import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "tandeos.db")
MIGRATION_PATH = os.path.join(os.path.dirname(__file__), "migration_003_calendario_tandeos.sql")


def seed_tandeos(db_target: str = DB_PATH):
    conn = sqlite3.connect(db_target)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    # Ejecutar migración 003 si las tablas no existen
    if os.path.exists(MIGRATION_PATH):
        with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
            cur.executescript(f.read())
    else:
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS sectores (
                id_sector INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                descripcion TEXT
            );
            CREATE TABLE IF NOT EXISTS colonias (
                id_colonia INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                codigo_postal TEXT NOT NULL,
                id_sector INTEGER,
                zona TEXT,
                FOREIGN KEY (id_sector) REFERENCES sectores(id_sector) ON UPDATE CASCADE ON DELETE RESTRICT
            );
            CREATE TABLE IF NOT EXISTS programacion_tandeos (
                id_programacion INTEGER PRIMARY KEY AUTOINCREMENT,
                id_colonia INTEGER NOT NULL,
                dia_semana TEXT NOT NULL CHECK (dia_semana IN ('Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo')),
                hora_inicio TEXT NOT NULL,
                hora_fin TEXT NOT NULL,
                estado_servicio TEXT NOT NULL CHECK (estado_servicio IN ('Activo', 'Suspendido', 'Mantenimiento')),
                fecha_actualizacion TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (id_colonia) REFERENCES colonias(id_colonia) ON UPDATE CASCADE ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_colonias_nombre ON colonias(nombre COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_colonias_cp ON colonias(codigo_postal);
            CREATE INDEX IF NOT EXISTS idx_programacion_colonia ON programacion_tandeos(id_colonia);
            """
        )

    # 1. Poblar 'Sector' histórico (compatibilidad)
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Sector'")
    if cur.fetchone():
        cur.execute("SELECT COUNT(*) FROM Sector")
        if cur.fetchone()[0] == 0:
            sectores = [
                ("Sector 1 - Zona Centro", "Red Gravedad Alta", "Disponible"),
                ("Sector 2 - Zona Oeste (Coapexpan)", "Red Bombeo Presión Media", "Parcial"),
                ("Sector 3 - Zona Este (Las Trancas / Ánimas)", "Red Mezcla Acuífero", "Disponible"),
                ("Sector 4 - Zona Norte (Progreso)", "Red Bombeo Tanque Alto", "No disponible"),
            ]
            cur.executemany(
                "INSERT INTO Sector (nombre_sector, red_hidraulica, disponibilidad) VALUES (?, ?, ?)",
                sectores,
            )

    # 2. Poblar 'sectores' (nueva estructura CU-001)
    cur.execute("SELECT COUNT(*) FROM sectores")
    if cur.fetchone()[0] == 0:
        sectores_nuevos = [
            ("Sector 1 - Zona Centro", "Red de Gravedad Alta - Cuadrante Histórico y Centro"),
            ("Sector 2 - Zona Oeste (Coapexpan)", "Red de Bombeo Presión Media - Laderas y Tanque Coapexpan"),
            ("Sector 3 - Zona Este (Las Trancas / Ánimas)", "Red de Mezcla Acuífero y Rebombeo Ánimas"),
            ("Sector 4 - Zona Norte (Progreso)", "Red de Bombeo Tanque Alto y Lomas"),
        ]
        cur.executemany(
            "INSERT INTO sectores (nombre, descripcion) VALUES (?, ?)",
            sectores_nuevos,
        )

    # Mapa de sectores
    cur.execute("SELECT id_sector, nombre FROM sectores")
    sector_map = {row[1]: row[0] for row in cur.fetchall()}

    # 3. Poblar 'colonias'
    cur.execute("SELECT COUNT(*) FROM colonias")
    if cur.fetchone()[0] == 0:
        colonias_data = [
            ("Centro", "91000", sector_map["Sector 1 - Zona Centro"], "Zona Centro"),
            ("Los Berros", "91000", sector_map["Sector 1 - Zona Centro"], "Zona Centro"),
            ("Coapexpan", "91070", sector_map["Sector 2 - Zona Oeste (Coapexpan)"], "Zona Oeste"),
            ("Salud", "91070", sector_map["Sector 2 - Zona Oeste (Coapexpan)"], "Zona Oeste"),
            ("Las Ánimas", "91190", sector_map["Sector 3 - Zona Este (Las Trancas / Ánimas)"], "Zona Este"),
            ("Las Trancas", "91194", sector_map["Sector 3 - Zona Este (Las Trancas / Ánimas)"], "Zona Este"),
            ("Progreso Macuiltépetl", "91130", sector_map["Sector 4 - Zona Norte (Progreso)"], "Zona Norte"),
        ]
        cur.executemany(
            "INSERT INTO colonias (nombre, codigo_postal, id_sector, zona) VALUES (?, ?, ?, ?)",
            colonias_data,
        )

    # Mapa de colonias
    cur.execute("SELECT id_colonia, nombre FROM colonias")
    colonia_map = {row[1]: row[0] for row in cur.fetchall()}

    # 4. Poblar 'programacion_tandeos' con datos reales (Centro, Las Ánimas, Coapexpan)
    cur.execute("SELECT COUNT(*) FROM programacion_tandeos")
    if cur.fetchone()[0] == 0:
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        programaciones_colonia = []

        # Centro (CP 91000): Activo Lun, Mié, Vie, Dom
        id_centro = colonia_map.get("Centro")
        if id_centro:
            for dia in dias:
                if dia in ["Lunes", "Miércoles", "Viernes", "Domingo"]:
                    estado = "Activo"
                    h_ini, h_fin = "06:00", "22:00"
                else:
                    estado = "Suspendido"
                    h_ini, h_fin = "00:00", "23:59"
                programaciones_colonia.append((id_centro, dia, h_ini, h_fin, estado))

        # Las Ánimas (CP 91190): Activo Lun, Jue, Sáb
        id_animas = colonia_map.get("Las Ánimas")
        if id_animas:
            for dia in dias:
                if dia in ["Lunes", "Jueves", "Sábado"]:
                    estado = "Activo"
                    h_ini, h_fin = "08:00", "21:00"
                else:
                    estado = "Suspendido"
                    h_ini, h_fin = "00:00", "23:59"
                programaciones_colonia.append((id_animas, dia, h_ini, h_fin, estado))

        # Coapexpan (CP 91070): Activo Mar, Jue, Sáb; Mantenimiento Dom; Suspendido otros
        id_coapexpan = colonia_map.get("Coapexpan")
        if id_coapexpan:
            for dia in dias:
                if dia in ["Martes", "Jueves", "Sábado"]:
                    estado = "Activo"
                    h_ini, h_fin = "07:00", "20:00"
                elif dia == "Domingo":
                    estado = "Mantenimiento"
                    h_ini, h_fin = "08:00", "16:00"
                else:
                    estado = "Suspendido"
                    h_ini, h_fin = "00:00", "23:59"
                programaciones_colonia.append((id_coapexpan, dia, h_ini, h_fin, estado))

        cur.executemany(
            """
            INSERT INTO programacion_tandeos (id_colonia, dia_semana, hora_inicio, hora_fin, estado_servicio)
            VALUES (?, ?, ?, ?, ?)
            """,
            programaciones_colonia,
        )

    conn.commit()
    conn.close()
    print("SEED_TANDEOS_COMPLETADO")


if __name__ == "__main__":
    seed_tandeos()

