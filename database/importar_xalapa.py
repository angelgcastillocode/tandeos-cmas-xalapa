#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migración: Importación del catálogo oficial de colonias reales de Xalapa.
Comisión Municipal de Agua Potable y Saneamiento (CMAS) - Tandeos.

Base de datos: database/tandeos.db
Archivo origen: database/colonias_xalapa.xls (Catálogo de Códigos Postales - SEPOMEX)
"""

import os
import sys
import html
import sqlite3
import csv
import io
from html.parser import HTMLParser
from typing import List, Tuple, Dict, Any

# Asegurar codificación UTF-8 en salida de consola en sistemas Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH_DEFAULT = os.path.join(BASE_DIR, "tandeos.db")
ORIGEN_PATH_DEFAULT = os.path.join(BASE_DIR, "colonias_xalapa.xls")


class SepomexHTMLParser(HTMLParser):
    """Parser para extraer celdas estructuradas de tablas HTML generadas por SEPOMEX / Correos de México."""

    def __init__(self):
        super().__init__()
        self.rows: List[List[str]] = []
        self._current_row: List[str] = []
        self._current_cell: List[str] = []
        self._in_cell: bool = False

    def handle_starttag(self, tag: str, attrs: list):
        tag_lower = tag.lower()
        if tag_lower in ("td", "th"):
            self._in_cell = True
            self._current_cell = []
        elif tag_lower == "tr":
            self._current_row = []

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if tag_lower in ("td", "th"):
            self._in_cell = False
            texto_celda = html.unescape("".join(self._current_cell).strip())
            self._current_row.append(texto_celda)
        elif tag_lower == "tr":
            if self._current_row:
                self.rows.append(self._current_row)

    def handle_data(self, data: str):
        if self._in_cell:
            self._current_cell.append(data)


def leer_archivo_texto(ruta_archivo: str) -> str:
    """Lee el archivo detectando de manera resiliente la codificación (UTF-8, Latin-1, CP1252)."""
    with open(ruta_archivo, "rb") as f:
        raw_bytes = f.read()

    # Intentar decodificar en orden preferente
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1", "iso-8859-1"):
        try:
            return raw_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("latin-1", errors="replace")


def extraer_registros_colonias(contenido: str) -> List[Dict[str, str]]:
    """
    Extrae los registros de colonias a partir de HTML (formato SEPOMEX .xls) o CSV estándar.
    Retorna lista de diccionarios con 'codigo_postal', 'tipo' y 'asentamiento'.
    """
    registros: List[Dict[str, str]] = []

    # 1. Si contiene estructura de tabla HTML
    if "<table" in contenido.lower() or "<tr" in contenido.lower():
        parser = SepomexHTMLParser()
        parser.feed(contenido)

        header_encontrado = False
        for row in parser.rows:
            if not header_encontrado:
                fila_texto = " ".join(c.lower() for c in row)
                if "postal" in fila_texto and ("asentamiento" in fila_texto or "municipio" in fila_texto):
                    header_encontrado = True
                continue

            # Columnas esperadas: [CP, Estado, Municipio, Ciudad, Tipo Asentamiento, Asentamiento, ...]
            if len(row) >= 6:
                cp = row[0].strip()
                tipo = row[4].strip() if len(row) > 4 else "Colonia"
                asentamiento = row[5].strip() if len(row) > 5 else row[1].strip()
                if cp and asentamiento:
                    registros.append({
                        "codigo_postal": cp,
                        "tipo": tipo,
                        "asentamiento": asentamiento,
                    })
    else:
        # 2. Formato CSV delimitado por comas
        reader = csv.reader(io.StringIO(contenido))
        header_encontrado = False
        for row in reader:
            if not row:
                continue
            if not header_encontrado:
                fila_texto = " ".join(c.lower() for c in row)
                if "postal" in fila_texto:
                    header_encontrado = True
                continue

            if len(row) >= 6:
                cp = row[0].strip()
                tipo = row[4].strip()
                asentamiento = row[5].strip()
                if cp and asentamiento:
                    registros.append({
                        "codigo_postal": cp,
                        "tipo": tipo,
                        "asentamiento": asentamiento,
                    })
            elif len(row) >= 2:
                if row[0].strip().isdigit() and len(row[0].strip()) == 5:
                    registros.append({
                        "codigo_postal": row[0].strip(),
                        "tipo": "Colonia",
                        "asentamiento": row[1].strip(),
                    })
                elif len(row) >= 2 and row[1].strip().isdigit() and len(row[1].strip()) == 5:
                    registros.append({
                        "codigo_postal": row[1].strip(),
                        "tipo": "Colonia",
                        "asentamiento": row[0].strip(),
                    })

    return registros


def determinar_sector_y_zona(codigo_postal: str, asentamiento: str = "") -> Tuple[int, str]:
    """
    Determina el sector y zona geográfica oficial de CMAS para una colonia de Xalapa
    a partir de su código postal y nomenclatura urbana.
    
    Sectores oficiales en CMAS:
    - Sector 1: Zona Centro (91000 - 91019)
    - Sector 2: Zona Oeste (Coapexpan, Salud) (91020 - 91079)
    - Sector 3: Zona Este (Las Trancas, Ánimas) (91150 - 91199)
    - Sector 4: Zona Norte (Progreso, Periferia) (91080 - 91149, >= 91200)
    """
    try:
        cp = int(codigo_postal)
    except (ValueError, TypeError):
        return (1, "Zona Centro")

    asentamiento_lower = asentamiento.lower()

    # Prioridad por palabras clave de cuadrantes emblemáticos de Xalapa
    if any(k in asentamiento_lower for k in ("ánimas", "animas", "trancas")):
        return (3, "Zona Este")
    if any(k in asentamiento_lower for k in ("coapexpan", "salud", "san bruno")):
        return (2, "Zona Oeste")
    if any(k in asentamiento_lower for k in ("centro", "berros")):
        return (1, "Zona Centro")

    # Mapeo por rangos oficiales de CP en el municipio de Xalapa
    if 91000 <= cp <= 91019:
        return (1, "Zona Centro")
    elif 91020 <= cp <= 91079:
        return (2, "Zona Oeste")
    elif 91080 <= cp <= 91149:
        return (4, "Zona Norte")
    elif 91150 <= cp <= 91199:
        return (3, "Zona Este")
    else:
        return (4, "Zona Norte")


def preparar_datos_colonias(registros: List[Dict[str, str]]) -> List[Tuple[str, str, int, str]]:
    """
    Prepara las tuplas (nombre, codigo_postal, id_sector, zona) para inserción en SQLite.
    Si existen registros homónimos con idéntico código postal, agrega el tipo de asentamiento
    para garantizar una clara distinción ciudadana (ej. 'El Haya (Colonia)' vs 'El Haya (Fraccionamiento)').
    """
    conteo_duplicados: Dict[Tuple[str, str], int] = {}
    for r in registros:
        clave = (r["asentamiento"], r["codigo_postal"])
        conteo_duplicados[clave] = conteo_duplicados.get(clave, 0) + 1

    filas_insercion: List[Tuple[str, str, int, str]] = []
    for r in registros:
        asentamiento = r["asentamiento"]
        cp = r["codigo_postal"]
        tipo = r["tipo"]

        if conteo_duplicados.get((asentamiento, cp), 0) > 1 and tipo:
            nombre_final = f"{asentamiento} ({tipo})"
        else:
            nombre_final = asentamiento

        id_sector, zona = determinar_sector_y_zona(cp, asentamiento)
        filas_insercion.append((nombre_final, cp, id_sector, zona))

    return filas_insercion


def migrar_colonias_xalapa(
    db_path: str = DB_PATH_DEFAULT,
    origen_path: str = ORIGEN_PATH_DEFAULT,
) -> int:
    """
    Ejecuta el proceso completo de migración e importación:
    1. Limpia registros de prueba anteriores en tablas dependientes ('programacion_tandeos', 'reportes_ciudadanos')
       y en la tabla 'colonias'.
    2. Lee e interpreta el catálogo oficial de Xalapa (SEPOMEX .xls / CSV) en UTF-8.
    3. Realiza la inserción masiva optimizada mediante consultas parametrizadas (?) bajo transacción ACID.
    4. Retorna el total de colonias reales importadas.
    """
    if not os.path.exists(origen_path):
        raise FileNotFoundError(f"No se encontró el archivo de origen: {origen_path}")
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"No se encontró la base de datos destino: {db_path}")

    # 1. Cargar y parsear archivo de colonias
    contenido = leer_archivo_texto(origen_path)
    registros = extraer_registros_colonias(contenido)
    if not registros:
        raise ValueError("No se encontraron registros válidos de colonias en el archivo origen.")

    filas_insercion = preparar_datos_colonias(registros)

    # 2. Conectar a SQLite y ejecutar dentro de una transacción segura
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    try:
        # Paso 1: Limpieza de registros semilla/prueba en tablas dependientes
        cur.execute("DELETE FROM programacion_tandeos")

        # Limpiar registros de prueba en reportes_ciudadanos si existe
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='reportes_ciudadanos'"
        )
        if cur.fetchone():
            cur.execute("DELETE FROM reportes_ciudadanos")

        # Limpiar tabla colonias
        cur.execute("DELETE FROM colonias")

        # Reiniciar contadores autoincrementables para tablas limpiadas
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
        )
        if cur.fetchone():
            cur.execute(
                "DELETE FROM sqlite_sequence WHERE name IN ('colonias', 'programacion_tandeos', 'reportes_ciudadanos')"
            )

        # Paso 2: Inserción masiva y optimizada con executemany y parámetros (?)
        cur.executemany(
            """
            INSERT INTO colonias (nombre, codigo_postal, id_sector, zona)
            VALUES (?, ?, ?, ?)
            """,
            filas_insercion,
        )

        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise exc
    finally:
        conn.close()

    return len(filas_insercion)


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH_DEFAULT
    origen = sys.argv[2] if len(sys.argv) > 2 else ORIGEN_PATH_DEFAULT

    print("==================================================================")
    print("MIGRACIÓN CMAS: Catálogo Oficial de Colonias Reales de Xalapa")
    print(f"Base de datos destino: {db}")
    print(f"Archivo origen: {origen}")
    print("==================================================================")

    try:
        total_importadas = migrar_colonias_xalapa(db_path=db, origen_path=origen)
        print(f"Total de colonias reales importadas: {total_importadas}")
        print("Migración finalizada exitosamente.")
    except Exception as error:
        print(f"ERROR DURANTE LA MIGRACIÓN: {error}", file=sys.stderr)
        sys.exit(1)
