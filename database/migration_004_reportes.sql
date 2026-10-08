-- Migración 004: Creación de la tabla de reportes ciudadanos e índices (CU-002)
CREATE TABLE IF NOT EXISTS reportes_ciudadanos (
    id_reporte INTEGER PRIMARY KEY AUTOINCREMENT,
    folio TEXT NOT NULL UNIQUE,
    id_colonia INTEGER NOT NULL,
    tipo_incidencia TEXT NOT NULL CHECK(tipo_incidencia IN ('Falta de agua', 'Fuga', 'Baja presión', 'Mantenimiento', 'Otro')),
    descripcion TEXT NOT NULL,
    nombre_ciudadano TEXT,
    telefono_contacto TEXT,
    id_usuario INTEGER,
    fecha_hora_reporte DATETIME NOT NULL DEFAULT (DATETIME('now', 'localtime')),
    estado TEXT NOT NULL DEFAULT 'Abierto' CHECK(estado IN ('Abierto', 'En proceso', 'Cerrado')),
    FOREIGN KEY (id_colonia) REFERENCES colonias(id_colonia),
    FOREIGN KEY (id_usuario) REFERENCES Usuario(id_usuario)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_rep_folio ON reportes_ciudadanos(folio);
CREATE INDEX IF NOT EXISTS idx_rep_usuario ON reportes_ciudadanos(id_usuario);
