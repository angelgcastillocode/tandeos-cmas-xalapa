PRAGMA foreign_keys = ON;

-- ==============================================================================
-- PROYECTO: PLATAFORMA DE TANDEOS CMAS XALAPA (EQUIPO MORADO)
-- ARCHIVO: database/seeds.sql
-- DESCRIPCIÓN: Datos semilla representativos de Xalapa, Veracruz.
-- ==============================================================================

-- 1. Roles del Sistema
INSERT INTO roles (id_rol, nombre_rol, descripcion) VALUES
    (1, 'Ciudadano', 'Usuario general con permisos de consulta de tandeos y levantamiento de reportes.'),
    (2, 'Operador', 'Personal técnico de CMAS encargado de actualizar tandeos y atender incidencias.'),
    (3, 'Administrador', 'Gestor de infraestructura hidráulica, catálogos de colonias y control de usuarios.');

-- 2. Usuarios Registrados
INSERT INTO usuarios (id_usuario, nombre_completo, email, password_hash, id_rol, fecha_registro, activo) VALUES
    (1, 'Angel Gabriel Castillo', 'angel.castillo@ciudadano.xalapa.mx', 'pbkdf2:sha256:600000$cmas$9f8e7d6c5b4a', 1, '2026-01-10 08:30:00', 1),
    (2, 'María Fernanda Hernández', 'mfernanda.hdez@ciudadano.xalapa.mx', 'pbkdf2:sha256:600000$cmas$1a2b3c4d5e6f', 1, '2026-01-12 10:15:00', 1),
    (3, 'Ing. Roberto Morales Vega', 'rmorales.operacion@cmasxalapa.gob.mx', 'pbkdf2:sha256:600000$cmas$7c8d9e0f1a2b', 2, '2026-01-05 07:00:00', 1),
    (4, 'Dra. Elena Vázquez Ruiz', 'evazquez.admin@cmasxalapa.gob.mx', 'pbkdf2:sha256:600000$cmas$3e4f5a6b7c8d', 3, '2026-01-02 09:00:00', 1);

-- 3. Sectores Hidráulicos de Xalapa
INSERT INTO sectores (id_sector, nombre_sector, zona, descripcion) VALUES
    (1, 'Sector 1 - Zona Centro Histórico', 'Centro', 'Abastecimiento prioritario para primer cuadro de la ciudad y zonas hospitalarias.'),
    (2, 'Sector 2 - Zona Sur Ánimas/Coapexpan', 'Sur', 'Cobertura residencial y comercial de la zona sur y salida a Coatepec.'),
    (3, 'Sector 3 - Zona Este Las Trancas', 'Este', 'Macrosector de crecimiento habitacional hacia Las Fuentes y Reserva Territorial.'),
    (4, 'Sector 4 - Zona Norte', 'Norte', 'Macrosector de alta demanda que abarca Progreso Macuiltépetl y Revolución.');

-- 4. Redes de Bombeo y Tanques de Regulación
INSERT INTO redes_bombeo (id_red, nombre_red, capacidad_m3, estado_operativo) VALUES
    (1, 'Red Tanque Alto y Lomas', 15000.0, 'Operativa'),
    (2, 'Red Planta Potabilizadora Xalapa', 28500.0, 'Operativa'),
    (3, 'Red Acueducto Huitzilapan', 32000.0, 'Operativa'),
    (4, 'Red Cerro del Estropajo', 12000.0, 'Mantenimiento');

-- 5. Colonias Representativas de Xalapa
INSERT INTO colonias (id_colonia, nombre_colonia, codigo_postal, id_sector, id_red) VALUES
    (1, 'Centro Histórico', '91000', 1, 2),
    (2, 'Progreso Macuiltépetl', '91110', 4, 1),
    (3, 'Revolución', '91100', 4, 3),
    (4, 'Jardines de las Ánimas', '91190', 2, 2),
    (5, 'Coapexpan', '91060', 2, 1),
    (6, 'Las Fuentes', '91097', 3, 3),
    (7, ' Lomas Verdes', '91098', 3, 4);

-- 6. Programación de Tandeos (0=Domingo, 1=Lunes, 2=Martes, 3=Miércoles, 4=Jueves, 5=Viernes, 6=Sábado)
INSERT INTO programacion_tandeo (id_tandeo, id_colonia, dia_semana, hora_inicio, hora_fin, estado_suministro) VALUES
    (1, 1, 1, '06:00', '22:00', 'Con servicio'),
    (2, 1, 2, '06:00', '22:00', 'Con servicio'),
    (3, 2, 1, '07:00', '19:00', 'Con servicio'),
    (4, 2, 2, '00:00', '23:59', 'Tandeo corte'),
    (5, 3, 1, '00:00', '23:59', 'Tandeo corte'),
    (6, 3, 2, '06:00', '20:00', 'Con servicio'),
    (7, 4, 3, '08:00', '21:00', 'Con servicio'),
    (8, 5, 4, '00:00', '23:59', 'Tandeo corte'),
    (9, 6, 5, '06:00', '18:00', 'Con servicio'),
    (10, 7, 6, '08:00', '16:00', 'Mantenimiento');

-- 7. Reportes de Incidencias Ciudadanas
INSERT INTO reportes_incidencias (id_reporte, folio_oficial, id_colonia, id_usuario, tipo_incidencia, descripcion, fecha_ingreso, estado_incidencia) VALUES
    (1, '#RPT-2026-00001', 2, 1, 'Falta de agua', 'Sin suministro desde hace 48 horas pese a calendario activo en calle Durango.', '2026-03-01 09:15:00', 'En atencion'),
    (2, '#RPT-2026-00002', 3, 2, 'Fuga', 'Fuga visible en banqueta sobre Av. Atenas Veracruzana esquina con calle Rébsamen.', '2026-03-01 11:40:00', 'Abierto'),
    (3, '#RPT-2026-00003', 5, 1, 'Baja presion', 'Presión insuficiente para subir a tinacos de segunda planta en zona Coapexpan.', '2026-03-02 08:20:00', 'Resuelto'),
    (4, '#RPT-2026-00004', 7, 2, 'Falta de agua', 'Corte prolongado por mantenimiento en Red Cerro del Estropajo.', '2026-03-02 14:10:00', 'Abierto');

