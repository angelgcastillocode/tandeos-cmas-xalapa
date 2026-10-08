-- Migración 002: Índices de rendimiento para búsqueda rápida de colonias y tandeos
CREATE INDEX IF NOT EXISTS idx_colonia_nombre ON Colonia(nombre_colonia);
CREATE INDEX IF NOT EXISTS idx_colonia_cp ON Colonia(codigo_postal);
CREATE INDEX IF NOT EXISTS idx_colonia_sector ON Colonia(id_sector);
CREATE INDEX IF NOT EXISTS idx_programacion_sector ON ProgramacionTandeo(id_sector);
