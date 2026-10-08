-- ============================================================================
-- Migración 005: Panel de Supervisión y Operación Técnica CMAS Xalapa
-- Índices para consultas dinámicas y tabla de auditoría/bitácora operativa
-- ============================================================================

-- 1. Índices de rendimiento sobre reportes ciudadanos
CREATE INDEX IF NOT EXISTS idx_rep_fecha ON reportes_ciudadanos(fecha_hora_reporte);
CREATE INDEX IF NOT EXISTS idx_rep_colonia ON reportes_ciudadanos(id_colonia);
CREATE INDEX IF NOT EXISTS idx_rep_estado ON reportes_ciudadanos(estado);
CREATE INDEX IF NOT EXISTS idx_rep_tipo ON reportes_ciudadanos(tipo_incidencia);
CREATE INDEX IF NOT EXISTS idx_rep_estado_fecha ON reportes_ciudadanos(estado, fecha_hora_reporte);

-- 2. Bitácora de supervisión y control operativo
CREATE TABLE IF NOT EXISTS bitacora_supervisor (
    id_bitacora INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario INTEGER NOT NULL,
    accion TEXT NOT NULL,
    folio_reporte TEXT,
    id_colonia INTEGER,
    observaciones TEXT,
    fecha_hora DATETIME NOT NULL DEFAULT (DATETIME('now', 'localtime')),
    FOREIGN KEY (id_usuario) REFERENCES Usuario(id_usuario) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (id_colonia) REFERENCES colonias(id_colonia) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_bitacora_usuario ON bitacora_supervisor(id_usuario);
CREATE INDEX IF NOT EXISTS idx_bitacora_fecha ON bitacora_supervisor(fecha_hora);
CREATE INDEX IF NOT EXISTS idx_bitacora_folio ON bitacora_supervisor(folio_reporte);
