-- ============================================================================
-- Migración 007: Asegurar campo 'telefono' en la tabla Usuario
-- Plataforma CMAS Tandeos - Registro Ciudadano
-- ============================================================================

-- En SQLite nativo, si la columna 'telefono' no existiera en una instalación previa:
-- ALTER TABLE Usuario ADD COLUMN telefono TEXT;
