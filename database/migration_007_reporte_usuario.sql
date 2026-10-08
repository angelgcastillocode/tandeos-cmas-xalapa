-- ============================================================================
-- Migración 007: Vinculación de usuario autenticado en reportes ciudadanos
-- Mitigación de spam/bots y trazabilidad de incidencias (CU-002)
-- ============================================================================

ALTER TABLE reportes_ciudadanos ADD COLUMN id_usuario INTEGER REFERENCES Usuario(id_usuario);
CREATE INDEX IF NOT EXISTS idx_rep_usuario ON reportes_ciudadanos(id_usuario);
