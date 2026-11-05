PRAGMA foreign_keys = ON;

-- ==============================================================================
-- PROYECTO: PLATAFORMA DE TANDEOS CMAS XALAPA (EQUIPO MORADO)
-- HITO 1: BASE DE DATOS RELACIONAL NORMALIZADA EN 3FN (7 TABLAS)
-- ARCHIVO: database/schema.sql
-- MOTOR: SQLite 3 (Desarrollo) / Compatible con PostgreSQL (Producción)
-- ==============================================================================

DROP TABLE IF EXISTS reportes_incidencias;
DROP TABLE IF EXISTS programacion_tandeo;
DROP TABLE IF EXISTS colonias;
DROP TABLE IF EXISTS redes_bombeo;
DROP TABLE IF EXISTS sectores;
DROP TABLE IF EXISTS usuarios;
DROP TABLE IF EXISTS roles;

-- ------------------------------------------------------------------------------
-- 1. TABLA: roles
-- Catálogo de perfiles de acceso y privilegios dentro de la plataforma CMAS.
-- ------------------------------------------------------------------------------
CREATE TABLE roles (
    id_rol INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_rol TEXT NOT NULL UNIQUE
        CHECK (nombre_rol IN ('Ciudadano', 'Operador', 'Administrador')),
    descripcion TEXT NOT NULL
);

-- ------------------------------------------------------------------------------
-- 2. TABLA: usuarios
-- Registro de ciudadanos, operadores técnicos de válvulas y administradores.
-- ------------------------------------------------------------------------------
CREATE TABLE usuarios (
    id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_completo TEXT NOT NULL
        CHECK (length(trim(nombre_completo)) >= 3),
    email TEXT NOT NULL UNIQUE
        CHECK (email LIKE '%_@__%.__%'),
    password_hash TEXT NOT NULL,
    id_rol INTEGER NOT NULL,
    fecha_registro DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    activo INTEGER NOT NULL DEFAULT 1
        CHECK (activo IN (0, 1)),
    CONSTRAINT fk_usuarios_rol
        FOREIGN KEY (id_rol) REFERENCES roles(id_rol)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

-- ------------------------------------------------------------------------------
-- 3. TABLA: sectores
-- División geográfica e hidráulica de la ciudad de Xalapa.
-- ------------------------------------------------------------------------------
CREATE TABLE sectores (
    id_sector INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_sector TEXT NOT NULL UNIQUE,
    zona TEXT NOT NULL
        CHECK (zona IN ('Norte', 'Sur', 'Centro', 'Este', 'Oeste', 'Periferia')),
    descripcion TEXT NOT NULL
);

-- ------------------------------------------------------------------------------
-- 4. TABLA: redes_bombeo
-- Infraestructura de tanques de almacenamiento, plantas y líneas de distribución.
-- ------------------------------------------------------------------------------
CREATE TABLE redes_bombeo (
    id_red INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_red TEXT NOT NULL UNIQUE,
    capacidad_m3 REAL NOT NULL
        CHECK (capacidad_m3 > 0),
    estado_operativo TEXT NOT NULL DEFAULT 'Operativa'
        CHECK (estado_operativo IN ('Operativa', 'Mantenimiento', 'Fuera de servicio'))
);

-- ------------------------------------------------------------------------------
-- 5. TABLA: colonias
-- Asentamientos de Xalapa vinculados a su sector hidráulico y red de bombeo (3FN).
-- ------------------------------------------------------------------------------
CREATE TABLE colonias (
    id_colonia INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_colonia TEXT NOT NULL UNIQUE,
    codigo_postal TEXT NOT NULL
        CHECK (length(codigo_postal) = 5),
    id_sector INTEGER NOT NULL,
    id_red INTEGER NOT NULL,
    CONSTRAINT fk_colonias_sector
        FOREIGN KEY (id_sector) REFERENCES sectores(id_sector)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CONSTRAINT fk_colonias_red
        FOREIGN KEY (id_red) REFERENCES redes_bombeo(id_red)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

-- ------------------------------------------------------------------------------
-- 6. TABLA: programacion_tandeo
-- Calendario operativo de suministro hidráulico por colonia y día (0=Dom .. 6=Sáb).
-- ------------------------------------------------------------------------------
CREATE TABLE programacion_tandeo (
    id_tandeo INTEGER PRIMARY KEY AUTOINCREMENT,
    id_colonia INTEGER NOT NULL,
    dia_semana INTEGER NOT NULL
        CHECK (dia_semana BETWEEN 0 AND 6),
    hora_inicio TEXT NOT NULL,
    hora_fin TEXT NOT NULL,
    estado_suministro TEXT NOT NULL
        CHECK (estado_suministro IN ('Con servicio', 'Tandeo corte', 'Mantenimiento')),
    CONSTRAINT uq_tandeo_colonia_dia_hora
        UNIQUE (id_colonia, dia_semana, hora_inicio),
    CONSTRAINT fk_tandeo_colonia
        FOREIGN KEY (id_colonia) REFERENCES colonias(id_colonia)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- ------------------------------------------------------------------------------
-- 7. TABLA: reportes_incidencias
-- Tickets ciudadanos con folio oficial único para atención de fugas y cortes.
-- ------------------------------------------------------------------------------
CREATE TABLE reportes_incidencias (
    id_reporte INTEGER PRIMARY KEY AUTOINCREMENT,
    folio_oficial TEXT NOT NULL UNIQUE
        CHECK (folio_oficial LIKE '#RPT-2026-%'),
    id_colonia INTEGER NOT NULL,
    id_usuario INTEGER NOT NULL,
    tipo_incidencia TEXT NOT NULL
        CHECK (tipo_incidencia IN ('Falta de agua', 'Fuga', 'Baja presion')),
    descripcion TEXT NOT NULL,
    fecha_ingreso DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado_incidencia TEXT NOT NULL DEFAULT 'Abierto'
        CHECK (estado_incidencia IN ('Abierto', 'En atencion', 'Resuelto')),
    CONSTRAINT fk_reportes_colonia
        FOREIGN KEY (id_colonia) REFERENCES colonias(id_colonia)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CONSTRAINT fk_reportes_usuario
        FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

-- ------------------------------------------------------------------------------
-- 8. ÍNDICES SIMPLES Y COMPUESTOS PARA OPTIMIZACIÓN DE CONSULTAS
-- ------------------------------------------------------------------------------
CREATE INDEX idx_colonias_cp
    ON colonias(codigo_postal);

CREATE INDEX idx_colonias_sector_red
    ON colonias(id_sector, id_red);

CREATE INDEX idx_tandeo_colonia_dia
    ON programacion_tandeo(id_colonia, dia_semana);

CREATE INDEX idx_reportes_colonia_estado
    ON reportes_incidencias(id_colonia, estado_incidencia);

