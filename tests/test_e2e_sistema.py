"""
Pruebas de Sistema End-to-End (E2E) — Entregable PRY07 (Hito 3)
Plataforma Cívica e Hidrológica de Tandeos y Reportes Ciudadanos CMAS Xalapa.

Valida de punta a punta los flujos multi-paso desde la interfaz HTTP y API REST
hasta la persistencia en SQLite 3 (con PRAGMA foreign_keys = ON) y la bitácora
de auditoría operativa, abarcando escenarios de éxito, validación de reglas de
negocio, controles de seguridad (RBAC, CSRF, SQLi, XSS) e integridad referencial.
"""

import json
import re
import pytest
from werkzeug.security import generate_password_hash

from app.repositories.db import get_db
from app.repositories.admin_repository import AdminRepository


# ============================================================================
# FIXTURES Y HELPERS DE CONFIGURACIÓN E2E
# ============================================================================

@pytest.fixture(autouse=True)
def setup_e2e_database(app):
    """
    Inicializa el esquema completo requerido para las pruebas de sistema E2E
    (migraciones 004 de reportes, 005 de supervisión y tabla de avisos oficiales)
    sobre la base de datos temporal aislada de `tests/conftest.py`.
    """
    with app.app_context():
        db = get_db()
        db.execute("PRAGMA foreign_keys = ON;")

        with open("database/migration_004_reportes.sql", "r", encoding="utf-8") as f:
            db.executescript(f.read())

        with open("database/migration_005_supervisor.sql", "r", encoding="utf-8") as f:
            db.executescript(f.read())

        # Garantizar la existencia de la tabla de avisos institucionales
        repo_admin = AdminRepository()
        repo_admin._garantizar_tabla_avisos()

        # Sembrar un usuario Supervisor adicional para pruebas cruzadas si no existe
        cur = db.cursor()
        cur.execute("SELECT id_usuario FROM Usuario WHERE correo = 'supervisor.e2e@cmas.gob.mx'")
        if not cur.fetchone():
            cur.execute(
                """
                INSERT INTO Usuario (nombre, correo, rol, credenciales, activo)
                VALUES (?, ?, ?, ?, 1)
                """,
                (
                    "Supervisor E2E CMAS",
                    "supervisor.e2e@cmas.gob.mx",
                    "Supervisor",
                    generate_password_hash("Password123"),
                ),
            )
        db.commit()


def _extraer_csrf_token(client, url: str = "/auth/login") -> str:
    """
    Realiza una petición GET a la ruta indicada y extrae el valor del campo
    oculto `csrf_token` renderizado en el formulario HTML.
    """
    resp = client.get(url)
    assert resp.status_code == 200, f"No se pudo cargar {url} para extraer CSRF (HTTP {resp.status_code})"
    match = re.search(rb'name="csrf_token"\s+value="([^"]+)"', resp.data)
    assert match is not None, f"No se encontró input csrf_token en {url}"
    return match.group(1).decode("utf-8")


# ============================================================================
# 1. ESCENARIO DE ÉXITO — FLUJO CIUDADANO PUNTA A PUNTA
# ============================================================================

def test_e2e_01_ciclo_ciudadano_completo_exito(client, app):
    """
    E2E-01 (Éxito): Valida el ciclo de vida completo de un ciudadano desde la consulta
    pública del calendario de tandeos, su registro e inicio de sesión con protección
    CSRF, hasta el levantamiento de un reporte de incidencia, la generación del folio
    oficial `RPT-2026-XXXXX` y su persistencia con estado inicial 'Abierto' en SQLite.
    """
    # Paso 1: Consulta pública del catálogo y tandeo de una colonia válida ("Centro")
    resp_consulta_web = client.get("/consulta?q=Centro")
    assert resp_consulta_web.status_code == 200
    assert b"Centro" in resp_consulta_web.data
    assert b"91000" in resp_consulta_web.data
    assert b"Sector 1" in resp_consulta_web.data

    resp_consulta_api = client.get("/api/v1/tandeos/buscar?q=Centro")
    assert resp_consulta_api.status_code == 200
    datos_api = json.loads(resp_consulta_api.data)
    assert datos_api["success"] is True
    assert datos_api["encontrado"] is True
    assert datos_api["colonia"]["nombre_colonia"] == "Centro"
    assert len(datos_api["programacion"]) >= 3

    # Paso 2: Registro de un nuevo ciudadano vía POST /auth/register con token CSRF
    csrf_reg = _extraer_csrf_token(client, "/auth/register")
    correo_ciudadano = "ciudadano.e2e@cmas.gob.mx"
    password_ciudadano = "ClaveSegura2026"

    resp_reg = client.post(
        "/auth/register",
        data={
            "nombre": "Valeria Xalapa E2E",
            "correo": correo_ciudadano,
            "telefono": "2281112233",
            "password": password_ciudadano,
            "csrf_token": csrf_reg,
        },
        follow_redirects=False,
    )
    assert resp_reg.status_code == 302
    assert resp_reg.headers["Location"].endswith("/auth/login")

    # Paso 3: Inicio de sesión con la cuenta recién registrada
    csrf_login = _extraer_csrf_token(client, "/auth/login")
    resp_login = client.post(
        "/auth/login",
        data={
            "correo": correo_ciudadano,
            "password": password_ciudadano,
            "csrf_token": csrf_login,
        },
        follow_redirects=False,
    )
    assert resp_login.status_code == 302
    assert resp_login.headers["Location"].endswith("/")

    # Paso 4: Levantar un reporte ciudadano válido (POST /reportar)
    csrf_rep = _extraer_csrf_token(client, "/reportar?colonia_id=1")
    descripcion_incidencia = (
        "Fuga severa de agua potable en la esquina de Enríquez y Clavijero, "
        "frente al parque Juárez, desperdiciando miles de litros."
    )
    resp_rep = client.post(
        "/reportar",
        data={
            "id_colonia": "1",
            "tipo_incidencia": "Fuga",
            "descripcion": descripcion_incidencia,
            "nombre_ciudadano": "Valeria Xalapa E2E",
            "telefono_contacto": "2281112233",
            "csrf_token": csrf_rep,
        },
        follow_redirects=False,
    )
    assert resp_rep.status_code == 302
    location = resp_rep.headers.get("Location", "")
    assert "/reporte/exito/RPT-2026-" in location

    folio_generado = location.split("/reporte/exito/")[1]
    assert re.match(r"^RPT-2026-[A-Z0-9]{5}$", folio_generado) is not None

    # Paso 5: Verificar la pantalla de confirmación del folio y el rastreador
    resp_confirmacion = client.get(location)
    assert resp_confirmacion.status_code == 200
    assert b"Reporte Registrado Correctamente" in resp_confirmacion.data
    assert folio_generado.encode("utf-8") in resp_confirmacion.data
    assert b"Abierto" in resp_confirmacion.data

    # Paso 6: Verificar directamente en SQLite que el reporte quedó persistido y vinculado al usuario
    with app.app_context():
        db = get_db()
        row_user = db.execute(
            "SELECT id_usuario, rol FROM Usuario WHERE correo = ?",
            (correo_ciudadano,),
        ).fetchone()
        assert row_user is not None
        assert row_user["rol"] == "Ciudadano"

        row_rep = db.execute(
            """
            SELECT folio, id_colonia, tipo_incidencia, descripcion, estado, id_usuario
            FROM reportes_ciudadanos
            WHERE folio = ?
            """,
            (folio_generado,),
        ).fetchone()
        assert row_rep is not None
        assert row_rep["folio"] == folio_generado
        assert row_rep["id_colonia"] == 1
        assert row_rep["tipo_incidencia"] == "Fuga"
        assert row_rep["estado"] == "Abierto"
        assert row_rep["id_usuario"] == row_user["id_usuario"]


# ============================================================================
# 2. ESCENARIO DE ÉXITO — FLUJO ADMINISTRATIVO Y SUPERVISIÓN
# ============================================================================

def test_e2e_02_ciclo_operativo_admin_y_supervision_exito(client, app):
    """
    E2E-02 (Éxito): Valida el flujo operativo institucional completo. Un usuario con rol
    'Administrador' inicia sesión, actualiza un calendario de tandeo, publica un aviso
    oficial, accede al Centro de Supervisión Técnica (validando jerarquía RBAC) y
    actualiza el estado de un reporte ciudadano verificando el cambio en SQLite y
    su asiento auditable en `bitacora_supervisor`.
    """
    # Preparar un reporte ciudadano abierto en la BD para que sea atendido en el flujo
    with app.app_context():
        db = get_db()
        cur = db.execute(
            """
            INSERT INTO reportes_ciudadanos
                (folio, id_colonia, tipo_incidencia, descripcion, nombre_ciudadano, fecha_hora_reporte, estado)
            VALUES
                ('RPT-2026-E2E02', 3, 'Falta de agua', 'Sin suministro en Las Ánimas durante horario activo programado', 'Ciudadano Ánimas', '2026-10-19 09:30:00', 'Abierto')
            """
        )
        id_reporte_prueba = cur.lastrowid
        db.commit()

    # Paso 1: Iniciar sesión con cuenta ADMINISTRADOR
    csrf_login = _extraer_csrf_token(client, "/auth/login")
    resp_login = client.post(
        "/auth/login",
        data={
            "correo": "admin@cmas.gob.mx",
            "password": "Password123",
            "csrf_token": csrf_login,
        },
        follow_redirects=False,
    )
    assert resp_login.status_code == 302
    assert resp_login.headers["Location"].endswith("/admin/dashboard")

    # Paso 2: Guardar/actualizar una programación de tandeo (POST /admin/tandeos/guardar)
    csrf_admin = _extraer_csrf_token(client, "/admin/dashboard")
    resp_tandeo = client.post(
        "/admin/tandeos/guardar",
        data={
            "id_colonia": "2",  # Los Berros
            "dia_semana": "Miércoles",
            "hora_inicio": "07:00",
            "hora_fin": "19:00",
            "estado_servicio": "Activo",
            "csrf_token": csrf_admin,
        },
        follow_redirects=True,
    )
    assert resp_tandeo.status_code == 200
    assert b"exitosamente" in resp_tandeo.data

    # Paso 3: Publicar un aviso oficial (POST /admin/avisos/crear)
    # Nota: admin_routes.py valida 'titulo', 'mensaje' y 'prioridad', y AdminService lee 'titulo', 'contenido' y 'prioridad'
    csrf_admin = _extraer_csrf_token(client, "/admin/dashboard")
    titulo_aviso = "Mantenimiento Preventivo Planta Potabilizadora Xalapa"
    texto_aviso = "Se informa a la ciudadanía del Sector 1 y 3 sobre maniobras de válvulas de 08:00 a 14:00 hrs."
    resp_aviso = client.post(
        "/admin/avisos/crear",
        data={
            "titulo": titulo_aviso,
            "mensaje": texto_aviso,
            "contenido": texto_aviso,
            "prioridad": "Alta",
            "id_sector": "3",
            "csrf_token": csrf_admin,
        },
        follow_redirects=True,
    )
    assert resp_aviso.status_code == 200
    assert b"publicado exitosamente" in resp_aviso.data

    # Paso 4: Navegar al Centro de Supervisión Técnica (GET /supervisor/dashboard) comprobando jerarquía RBAC
    resp_sup_dash = client.get("/supervisor/dashboard")
    assert resp_sup_dash.status_code == 200
    assert b"Centro de Supervisi\xc3\xb3n T\xc3\xa9cnica" in resp_sup_dash.data
    assert b"RPT-2026-E2E02" in resp_sup_dash.data

    # Paso 5: Actualizar el estado del reporte ciudadano desde supervisión a 'En proceso'
    csrf_sup = _extraer_csrf_token(client, "/supervisor/dashboard")
    observacion_operativa = "Se envía cuadrilla hidráulica #4 para purga de línea en Las Ánimas."
    resp_cambio_estado = client.post(
        f"/supervisor/reporte/{id_reporte_prueba}/estado",
        data={
            "nuevo_estado": "En proceso",
            "observaciones": observacion_operativa,
            "csrf_token": csrf_sup,
        },
        follow_redirects=True,
    )
    assert resp_cambio_estado.status_code == 200
    assert b"actualizado a &#39;En proceso&#39; exitosamente" in resp_cambio_estado.data or b"actualizado" in resp_cambio_estado.data

    # Paso 6: Verificar persistencia en SQLite de tandeo, aviso, estado del reporte y bitácora de supervisión
    with app.app_context():
        db = get_db()

        # 6.1 Verificar programación de tandeo guardada
        row_tandeo = db.execute(
            """
            SELECT hora_inicio, hora_fin, estado_servicio
            FROM programacion_tandeos
            WHERE id_colonia = 2 AND dia_semana = 'Miércoles'
            """
        ).fetchone()
        assert row_tandeo is not None
        assert row_tandeo["hora_inicio"] == "07:00"
        assert row_tandeo["hora_fin"] == "19:00"
        assert row_tandeo["estado_servicio"] == "Activo"

        # 6.2 Verificar aviso institucional publicado
        row_aviso = db.execute(
            "SELECT titulo, prioridad, id_sector, activo FROM avisos WHERE titulo = ?",
            (titulo_aviso,),
        ).fetchone()
        assert row_aviso is not None
        assert row_aviso["prioridad"] == "Alta"
        assert row_aviso["id_sector"] == 3
        assert row_aviso["activo"] == 1

        # 6.3 Verificar actualización de estado del reporte
        row_rep = db.execute(
            "SELECT estado FROM reportes_ciudadanos WHERE id_reporte = ?",
            (id_reporte_prueba,),
        ).fetchone()
        assert row_rep is not None
        assert row_rep["estado"] == "En proceso"

        # 6.4 Verificar asiento en bitácora de supervisión (`bitacora_supervisor`)
        row_bitacora = db.execute(
            """
            SELECT id_usuario, accion, folio_reporte, id_colonia, observaciones
            FROM bitacora_supervisor
            WHERE folio_reporte = 'RPT-2026-E2E02'
            ORDER BY id_bitacora DESC
            LIMIT 1
            """
        ).fetchone()
        assert row_bitacora is not None
        assert "Abierto -> En proceso" in row_bitacora["accion"]
        assert row_bitacora["id_colonia"] == 3
        assert observacion_operativa in row_bitacora["observaciones"]


# ============================================================================
# 3. ESCENARIO DE FALLO — RESTRICCIONES DE DOMINIO Y FORMULARIOS
# ============================================================================

def test_e2e_03_validacion_reglas_negocio_y_formularios_fallo(client, app):
    """
    E2E-03 (Fallo Controlado): Verifica que las reglas de negocio rechacen entradas
    inválidas sin corromper la base de datos ni provocar errores HTTP 500:
    - Registro con correo electrónico duplicado.
    - Envío de reporte con descripción menor a 15 caracteres o tipo de incidencia inválido.
    - Consulta pública de colonia inexistente, texto vacío o código postal incompleto.
    """
    # 1. Intentar registrar un usuario con correo duplicado (admin@cmas.gob.mx ya existe en seed)
    csrf_reg = _extraer_csrf_token(client, "/auth/register")
    resp_dup = client.post(
        "/auth/register",
        data={
            "nombre": "Usuario Duplicado",
            "correo": "admin@cmas.gob.mx",
            "telefono": "2281234567",
            "password": "Password123",
            "csrf_token": csrf_reg,
        },
        follow_redirects=True,
    )
    assert resp_dup.status_code == 200
    assert b"ya se encuentra registrado" in resp_dup.data

    with app.app_context():
        db = get_db()
        conteo_usuarios = db.execute(
            "SELECT COUNT(*) AS total FROM Usuario WHERE correo = 'admin@cmas.gob.mx'"
        ).fetchone()["total"]
        assert conteo_usuarios == 1, "No debe duplicarse el registro de usuario en SQLite"

    # 2. Autenticar sesión ciudadana para probar validaciones del formulario de reportes
    with client.session_transaction() as sess:
        sess["usuario_id"] = 1
        sess["usuario_nombre"] = "Ciudadano Validador"
        sess["usuario_rol"] = "Ciudadano"

    # 2.1 Intentar enviar reporte con descripción demasiado corta (< 15 caracteres)
    csrf_rep = _extraer_csrf_token(client, "/reportar")
    resp_desc_corta = client.post(
        "/reportar",
        data={
            "id_colonia": "1",
            "tipo_incidencia": "Falta de agua",
            "descripcion": "Sin agua hoy",  # 12 caracteres (< 15)
            "csrf_token": csrf_rep,
        },
        follow_redirects=False,
    )
    assert resp_desc_corta.status_code == 400
    assert b"al menos 15 caracteres" in resp_desc_corta.data

    # 2.2 Intentar enviar reporte con tipo de incidencia inválido
    resp_tipo_invalido = client.post(
        "/reportar",
        data={
            "id_colonia": "1",
            "tipo_incidencia": "Sabotaje Espacial",
            "descripcion": "Descripción suficientemente larga para superar quince caracteres.",
            "csrf_token": csrf_rep,
        },
        follow_redirects=False,
    )
    assert resp_tipo_invalido.status_code == 400
    assert b"El tipo de incidencia debe ser uno de los siguientes" in resp_tipo_invalido.data

    # Verificar en SQLite que ninguno de los dos reportes inválidos fue insertado
    with app.app_context():
        db = get_db()
        total_rep = db.execute("SELECT COUNT(*) AS total FROM reportes_ciudadanos").fetchone()["total"]
        assert total_rep == 0, "Los reportes rechazados por validación no deben insertarse en SQLite"

    # 3. Consultar colonia inexistente, texto vacío o término demasiado corto
    resp_vacio = client.get("/consulta?q=")
    assert resp_vacio.status_code == 200

    resp_corto = client.get("/consulta?q=a")
    assert resp_corto.status_code == 400
    assert b"al menos 2 caracteres" in resp_corto.data

    resp_inexistente = client.get("/consulta?q=ColoniaInexistenteXalapa2026")
    assert resp_inexistente.status_code == 200
    assert b"No encontramos esa colonia" in resp_inexistente.data

    resp_api_inexistente = client.get("/api/v1/tandeos/buscar?q=ColoniaInexistenteXalapa2026")
    assert resp_api_inexistente.status_code == 200
    json_inex = json.loads(resp_api_inexistente.data)
    assert json_inex["success"] is True
    assert json_inex["encontrado"] is False
    assert json_inex["programacion"] == []


# ============================================================================
# 4. ESCENARIO DE FALLO — SEGURIDAD, RBAC, CSRF E INYECCIÓN (SQLi / XSS)
# ============================================================================

def test_e2e_04_seguridad_rbac_csrf_inyeccion_fallo(client, app):
    """
    E2E-04 (Fallo Controlado / Seguridad): Valida los mecanismos de defensa activa:
    - Control de acceso RBAC: bloqueo HTTP 403 cuando un 'Ciudadano' intenta acceder
      a `/admin/dashboard` o `/supervisor/dashboard`.
    - Protección CSRF: rechazo de peticiones POST críticas que omiten `csrf_token`.
    - Prevención de SQL Injection (`' OR '1'='1`) y neutralización XSS (`<script>`).
    """
    # Sembrar un reporte base para probar el bloqueo CSRF en supervisión
    with app.app_context():
        db = get_db()
        cur = db.execute(
            """
            INSERT INTO reportes_ciudadanos
                (folio, id_colonia, tipo_incidencia, descripcion, fecha_hora_reporte, estado)
            VALUES
                ('RPT-2026-SEC01', 1, 'Fuga', 'Reporte base para prueba de seguridad CSRF', datetime('now'), 'Abierto')
            """
        )
        id_rep_sec = cur.lastrowid
        db.commit()

    # 1. Verificación RBAC: Sesión activa con rol CIUDADANO intentando acceder a paneles restringidos
    with client.session_transaction() as sess:
        sess["usuario_id"] = 99
        sess["usuario_nombre"] = "Ciudadano Sin Privilegios"
        sess["usuario_rol"] = "Ciudadano"

    resp_rbac_admin = client.get("/admin/dashboard")
    assert resp_rbac_admin.status_code == 403

    resp_rbac_sup = client.get("/supervisor/dashboard")
    assert resp_rbac_sup.status_code == 403

    resp_rbac_admin_api = client.get("/admin/api/metricas")
    assert resp_rbac_admin_api.status_code == 403

    resp_rbac_sup_api = client.get("/supervisor/api/metricas")
    assert resp_rbac_sup_api.status_code == 403

    # 2. Protección CSRF en endpoints POST críticos omitiendo el token CSRF
    # 2.1 POST /auth/logout sin csrf_token (con sesión de ciudadano)
    resp_logout_nocsrf = client.post("/auth/logout", data={}, follow_redirects=True)
    assert b"Acci\xc3\xb3n no permitida" in resp_logout_nocsrf.data

    # 2.2 POST /admin/tandeos/guardar sin csrf_token (con sesión de Administrador)
    with client.session_transaction() as sess:
        sess["usuario_id"] = 1
        sess["usuario_nombre"] = "Admin Test"
        sess["usuario_rol"] = "Administrador"
        sess.pop("_csrf_token", None)

    resp_tandeo_nocsrf = client.post(
        "/admin/tandeos/guardar",
        data={
            "id_colonia": "1",
            "dia_semana": "Lunes",
            "hora_inicio": "08:00",
            "hora_fin": "14:00",
            "estado_servicio": "Suspendido",
            # Sin csrf_token
        },
        follow_redirects=True,
    )
    assert b"Token CSRF inv\xc3\xa1lido" in resp_tandeo_nocsrf.data

    # 2.3 POST /supervisor/reporte/<id>/estado sin csrf_token
    resp_sup_nocsrf = client.post(
        f"/supervisor/reporte/{id_rep_sec}/estado",
        data={"nuevo_estado": "Cerrado"},
        follow_redirects=True,
    )
    assert b"token CSRF es inv\xc3\xa1lido" in resp_sup_nocsrf.data

    # Confirmar que el estado del reporte no fue alterado por la petición sin CSRF
    with app.app_context():
        db = get_db()
        estado_actual = db.execute(
            "SELECT estado FROM reportes_ciudadanos WHERE id_reporte = ?",
            (id_rep_sec,),
        ).fetchone()["estado"]
        assert estado_actual == "Abierto"

    # 2.4 POST /reportar sin sesión autenticada (bloqueo de acceso anónimo)
    with client.session_transaction() as sess:
        sess.clear()

    resp_rep_anon = client.post(
        "/reportar",
        data={
            "id_colonia": "1",
            "tipo_incidencia": "Fuga",
            "descripcion": "Intento de reporte sin sesión ni token CSRF activo",
        },
        follow_redirects=False,
    )
    assert resp_rep_anon.status_code in (302, 400, 403)
    if resp_rep_anon.status_code == 302:
        assert "/auth/login" in resp_rep_anon.headers.get("Location", "")

    # 3. Prevención de SQL Injection en buscador y XSS en descripción de reporte
    payload_sqli = "' OR '1'='1'; DROP TABLE colonias; --"
    resp_sqli_web = client.get(f"/consulta?q={payload_sqli}")
    assert resp_sqli_web.status_code in (200, 400)

    resp_sqli_api = client.get(f"/api/v1/tandeos/buscar?q={payload_sqli}")
    assert resp_sqli_api.status_code in (200, 400)

    # Confirmar que la tabla `colonias` permanece íntegra tras el intento de SQLi
    with app.app_context():
        db = get_db()
        total_colonias = db.execute("SELECT COUNT(*) AS total FROM colonias").fetchone()["total"]
        assert total_colonias >= 4

    # Enviar payload XSS en descripción de reporte ciudadano autenticado
    with client.session_transaction() as sess:
        sess["usuario_id"] = 1
        sess["usuario_nombre"] = "Auditor XSS"
        sess["usuario_rol"] = "Ciudadano"

    csrf_xss = _extraer_csrf_token(client, "/reportar")
    payload_xss = "<script>alert('xss')</script>Fuga crítica de agua limpia en calle principal del Centro"
    resp_xss = client.post(
        "/reportar",
        data={
            "id_colonia": "1",
            "tipo_incidencia": "Fuga",
            "descripcion": payload_xss,
            "nombre_ciudadano": "<img src=x onerror=alert(1)>Ciudadano XSS",
            "csrf_token": csrf_xss,
        },
        follow_redirects=True,
    )
    assert resp_xss.status_code == 200
    # El script ejecutable crudo NO debe aparecer en la respuesta HTML ni en la base de datos
    assert b"<script>alert('xss')</script>" not in resp_xss.data
    assert b"<img src=x onerror=alert(1)>" not in resp_xss.data

    with app.app_context():
        db = get_db()
        rep_xss = db.execute(
            "SELECT descripcion, nombre_ciudadano FROM reportes_ciudadanos ORDER BY id_reporte DESC LIMIT 1"
        ).fetchone()
        assert rep_xss is not None
        assert "<script>" not in rep_xss["descripcion"]
        assert "<img" not in (rep_xss["nombre_ciudadano"] or "")


# ============================================================================
# 5. ESCENARIO DE FALLO — INTEGRIDAD REFERENCIAL Y DATOS INVÁLIDOS EN BD
# ============================================================================

def test_e2e_05_integridad_referencial_y_datos_invalidos_fallo(client, app):
    """
    E2E-05 (Fallo Controlado / Integridad Referencial): Verifica que al enviar un
    identificador de colonia inexistente (`id_colonia = 999999`) tanto en el registro
    de reportes ciudadanos como en la programación administrativa de tandeos, el
    sistema intercepte la restricción de existencia / llave foránea (`FOREIGN KEY`) y
    responda de manera controlada sin exponer stack traces de Python o SQLite.
    """
    # 1. Intentar registrar un reporte ciudadano con `id_colonia = 999999` (inexistente)
    with client.session_transaction() as sess:
        sess["usuario_id"] = 1
        sess["usuario_nombre"] = "Ciudadano FK Test"
        sess["usuario_rol"] = "Ciudadano"

    csrf_rep = _extraer_csrf_token(client, "/reportar")
    resp_rep_fk = client.post(
        "/reportar",
        data={
            "id_colonia": "999999",
            "tipo_incidencia": "Fuga",
            "descripcion": "Fuga reportada hacia una colonia cuyo ID no existe en el catálogo.",
            "csrf_token": csrf_rep,
        },
        follow_redirects=False,
    )
    assert resp_rep_fk.status_code == 400
    assert b"no existe en el registro municipal" in resp_rep_fk.data
    # Garantizar que no se filtran trazas internas de Python o SQLite
    assert b"Traceback (most recent call last)" not in resp_rep_fk.data
    assert b"sqlite3.IntegrityError" not in resp_rep_fk.data

    # 2. Intentar guardar una programación de tandeo con `id_colonia = 999999` como Administrador
    with client.session_transaction() as sess:
        sess["usuario_id"] = 1
        sess["usuario_nombre"] = "Admin FK Test"
        sess["usuario_rol"] = "Administrador"

    csrf_admin = _extraer_csrf_token(client, "/admin/dashboard")
    resp_tandeo_fk = client.post(
        "/admin/tandeos/guardar",
        data={
            "id_colonia": "999999",
            "dia_semana": "Lunes",
            "hora_inicio": "08:00",
            "hora_fin": "20:00",
            "estado_servicio": "Activo",
            "csrf_token": csrf_admin,
        },
        follow_redirects=True,
    )
    assert resp_tandeo_fk.status_code == 200
    assert b"no existe" in resp_tandeo_fk.data
    assert b"Traceback (most recent call last)" not in resp_tandeo_fk.data
    assert b"sqlite3.IntegrityError" not in resp_tandeo_fk.data

    # 3. Verificación directa en SQLite: ningún registro huérfano con id_colonia = 999999 debe existir
    with app.app_context():
        db = get_db()
        rep_huerfano = db.execute(
            "SELECT COUNT(*) AS total FROM reportes_ciudadanos WHERE id_colonia = 999999"
        ).fetchone()["total"]
        assert rep_huerfano == 0

        tandeo_huerfano = db.execute(
            "SELECT COUNT(*) AS total FROM programacion_tandeos WHERE id_colonia = 999999"
        ).fetchone()["total"]
        assert tandeo_huerfano == 0
