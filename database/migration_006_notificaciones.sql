-- ============================================================================
-- Migración 006: Sistema de Notificaciones y Alertas CMAS Xalapa
-- Tablas para preferencias de usuario, cola de notificaciones, auditoría histórica
-- e índices de optimización de consultas.
-- ============================================================================

-- 1. Tabla de Preferencias de Notificación de Usuario
CREATE TABLE IF NOT EXISTS usuario_preferencias (
    id_preferencia INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario INTEGER NOT NULL UNIQUE,
    notif_email BOOLEAN NOT NULL DEFAULT 1,
    notif_sms BOOLEAN NOT NULL DEFAULT 0,
    id_colonia INTEGER,
    fecha_actualizacion DATETIME NOT NULL DEFAULT (DATETIME('now', 'localtime')),
    FOREIGN KEY (id_usuario) REFERENCES Usuario(id_usuario) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (id_colonia) REFERENCES colonias(id_colonia) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_usr_pref_usuario ON usuario_preferencias(id_usuario);
CREATE INDEX IF NOT EXISTS idx_usr_pref_colonia ON usuario_preferencias(id_colonia);

-- 2. Tabla de Historial y Cola de Notificaciones
CREATE TABLE IF NOT EXISTS notificaciones_historial (
    id_notificacion INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario INTEGER NOT NULL,
    tipo TEXT NOT NULL CHECK(tipo IN (
        'recordatorio_corte',
        'inicio_tandeo',
        'cambio_programacion',
        'suspension',
        'mantenimiento',
        'contingencia',
        'confirmacion_reporte'
    )),
    canal TEXT NOT NULL CHECK(canal IN ('email', 'sms')),
    mensaje TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'Pendiente' CHECK(estado IN ('Pendiente', 'Procesando', 'Enviado', 'Error')),
    fecha_generacion DATETIME NOT NULL DEFAULT (DATETIME('now', 'localtime')),
    fecha_envio DATETIME,
    motivo_error TEXT,
    FOREIGN KEY (id_usuario) REFERENCES Usuario(id_usuario) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notif_usuario ON notificaciones_historial(id_usuario);
CREATE INDEX IF NOT EXISTS idx_notif_estado ON notificaciones_historial(estado);
CREATE INDEX IF NOT EXISTS idx_notif_fecha_gen ON notificaciones_historial(fecha_generacion);
CREATE INDEX IF NOT EXISTS idx_notif_tipo ON notificaciones_historial(tipo);
CREATE INDEX IF NOT EXISTS idx_notif_canal ON notificaciones_historial(canal);

-- 3. Tabla de Bitácora de Auditoría Histórica de Notificaciones (Transiciones de Estado)
CREATE TABLE IF NOT EXISTS notificaciones_bitacora (
    id_bitacora INTEGER PRIMARY KEY AUTOINCREMENT,
    id_notificacion INTEGER NOT NULL,
    estado_anterior TEXT,
    estado_nuevo TEXT NOT NULL,
    detalle TEXT,
    fecha_cambio DATETIME NOT NULL DEFAULT (DATETIME('now', 'localtime')),
    FOREIGN KEY (id_notificacion) REFERENCES notificaciones_historial(id_notificacion) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bitacora_notif ON notificaciones_bitacora(id_notificacion);
CREATE INDEX IF NOT EXISTS idx_bitacora_fecha ON notificaciones_bitacora(fecha_cambio);

-- 4. Poblado inicial de preferencias a partir de usuarios existentes
INSERT OR IGNORE INTO usuario_preferencias (id_usuario, notif_email, notif_sms)
SELECT id_usuario, COALESCE(notif_email, 1), COALESCE(notif_sms, 0)
FROM Usuario;
