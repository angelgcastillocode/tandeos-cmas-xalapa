-- Migración 003: Tablas optimizadas para consulta y calendario semanal de tandeos (CU-001)

-- 1. Tabla de Sectores
CREATE TABLE IF NOT EXISTS sectores (
    id_sector INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    descripcion TEXT
);

-- 2. Tabla de Colonias
CREATE TABLE IF NOT EXISTS colonias (
    id_colonia INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    codigo_postal TEXT NOT NULL,
    id_sector INTEGER,
    zona TEXT,
    FOREIGN KEY (id_sector) REFERENCES sectores(id_sector) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- 3. Tabla de Programación de Tandeos por Colonia
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

-- 4. Índices Obligatorios para Optimización de Consultas
CREATE INDEX IF NOT EXISTS idx_colonias_nombre ON colonias(nombre COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_colonias_cp ON colonias(codigo_postal);
CREATE INDEX IF NOT EXISTS idx_programacion_colonia ON programacion_tandeos(id_colonia);
