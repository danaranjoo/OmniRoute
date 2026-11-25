"""
Backend FastAPI para el sistema de gestión de alarmas.
Prueba técnica Full Stack - Desarrollador Python

Arquitectura: API REST completamente desacoplada del Frontend.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from dateutil import parser as date_parser
from collections import defaultdict
from pathlib import Path
import pandas as pd
import sqlite3
import io
import csv
import os

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "alarmas.db"
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = FastAPI(
    title="Sistema de Alarmas - API",
    description="API REST para gestión, categorización y resumen de alarmas de red",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir el frontend estático (opcional, facilita la demo)
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------
class AlarmaResponse(BaseModel):
    id_alarma: str
    tech_2g: int
    tech_3g: int
    tech_4g: int
    fecha_creacion: str
    municipio: str
    departamento: str
    notificada: str
    duracion_horas: float
    duracion_formateada: str
    criticidad: str  # NORMAL | WARN | CRITICO


# ---------------------------------------------------------------------------
# Base de datos SQLite (persistencia simple)
# ---------------------------------------------------------------------------
def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crea la tabla si no existe."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alarmas (
                id_alarma TEXT PRIMARY KEY,
                tech_2g INTEGER,
                tech_3g INTEGER,
                tech_4g INTEGER,
                fecha_creacion TEXT,
                fecha_creacion_dt TEXT,
                municipio TEXT,
                departamento TEXT,
                notificada TEXT
            )
        """)
        conn.commit()


init_db()


def guardar_alarmas(lista: List[Dict[str, Any]]):
    """Reemplaza todas las alarmas en la BD."""
    with get_connection() as conn:
        conn.execute("DELETE FROM alarmas")
        for a in lista:
            conn.execute(
                """
                INSERT INTO alarmas
                (id_alarma, tech_2g, tech_3g, tech_4g, fecha_creacion,
                 fecha_creacion_dt, municipio, departamento, notificada)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    a["id_alarma"],
                    a["tech_2g"],
                    a["tech_3g"],
                    a["tech_4g"],
                    a["fecha_creacion"],
                    a["fecha_creacion_dt"],
                    a["municipio"],
                    a["departamento"],
                    a["notificada"],
                ),
            )
        conn.commit()


def cargar_alarmas_desde_db() -> List[Dict[str, Any]]:
    """Lee todas las alarmas de la BD."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM alarmas").fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Utilidades de negocio
# ---------------------------------------------------------------------------
def parse_fecha(fecha_str: str) -> datetime:
    """
    Parsea fechas del formato del CSV:
    09-OCT-26 10.12.56.000000000 PM  →  2026-10-09 22:12:56
    """
    try:
        parts = fecha_str.strip().split()
        if len(parts) >= 3:
            date_part = parts[0]
            time_part = parts[1]
            ampm = parts[2]
            # Tomar solo HH.MM.SS y convertir puntos a dos puntos
            time_clean = ".".join(time_part.split(".")[:3]).replace(".", ":")
            cleaned = f"{date_part} {time_clean} {ampm}"
            return date_parser.parse(cleaned)
        return date_parser.parse(fecha_str)
    except Exception:
        return datetime.now()


def calcular_duracion(fecha_creacion: datetime) -> tuple[float, str]:
    """Devuelve (horas_float, texto_legible)."""
    ahora = datetime.now()
    delta = ahora - fecha_creacion
    horas = delta.total_seconds() / 3600
    dias = int(horas // 24)
    horas_rest = int(horas % 24)
    minutos = int((delta.total_seconds() % 3600) // 60)
    if dias > 0:
        formateada = f"{dias}d {horas_rest}h {minutos}m"
    else:
        formateada = f"{horas_rest}h {minutos}m"
    return round(horas, 2), formateada


def aplicar_logica_criticidad(
    tech_2g: int,
    tech_3g: int,
    tech_4g: int,
    notificada: str,
    duracion_horas: float,
) -> str:
    """
    ========================================================================
    LÓGICA DE NEGOCIO – PROGRAMADA EN SU TOTALIDAD SIN AYUDA DE IA
    (función a sustentar en la entrevista)
    ========================================================================

    Condiciones base (deben cumplirse TODAS):

    1. Disponibilidad de Tecnologías:
       Los campos 2G, 3G y 4G deben tener valor >= 0.

    2. Capacidad al Límite:
       Al menos UNA de las tecnologías disponibles debe ser exactamente 100.

    3. Estado de Notificación:
       El campo NOTIFICADA debe ser 'N' (no notificada).

    Niveles de alerta según tiempo transcurrido desde FECHA_CREACION:

    - WARN:    condiciones base + duración > 1 hora  Y  duración <= 24 horas
    - CRITICO: condiciones base + duración > 24 horas
    - NORMAL:  cualquier otro caso
    """
    # --- 1. Valores de tecnología válidos (>= 0) ---
    if tech_2g < 0 or tech_3g < 0 or tech_4g < 0:
        return "NORMAL"

    # --- 2. Al menos una tecnología en capacidad máxima (100) ---
    if not (tech_2g == 100 or tech_3g == 100 or tech_4g == 100):
        return "NORMAL"

    # --- 3. Debe estar sin notificar ---
    if notificada.upper().strip() != "N":
        return "NORMAL"

    # --- Clasificación por tiempo ---
    if duracion_horas > 24:
        return "CRITICO"
    if duracion_horas > 1:
        return "WARN"
    return "NORMAL"


def procesar_fila(row: Dict[str, str]) -> Dict[str, Any]:
    """Transforma una fila del CSV en un diccionario listo para guardar/mostrar."""
    try:
        tech_2g = int(row.get("2G", 0) or 0)
        tech_3g = int(row.get("3G", 0) or 0)
        tech_4g = int(row.get("4G", 0) or 0)
    except (ValueError, TypeError):
        tech_2g = tech_3g = tech_4g = 0

    fecha_str = row.get("FECHA_CREACION", "")
    fecha_dt = parse_fecha(fecha_str)
    notificada = str(row.get("NOTIFICADA", "N")).strip()

    return {
        "id_alarma": str(row.get("ID_ALARMA", "")),
        "tech_2g": tech_2g,
        "tech_3g": tech_3g,
        "tech_4g": tech_4g,
        "fecha_creacion": fecha_str,
        "fecha_creacion_dt": fecha_dt.isoformat(),
        "municipio": str(row.get("MUNICIPIO", "")).strip('"'),
        "departamento": str(row.get("DEPARTAMENTO", "")).strip('"'),
        "notificada": notificada,
    }


def enriquecer_alarma(a: Dict[str, Any]) -> Dict[str, Any]:
    """Calcula duración y criticidad en tiempo real a partir de un registro de BD."""
    fecha_dt = datetime.fromisoformat(a["fecha_creacion_dt"])
    dur_h, dur_fmt = calcular_duracion(fecha_dt)
    criticidad = aplicar_logica_criticidad(
        a["tech_2g"], a["tech_3g"], a["tech_4g"], a["notificada"], dur_h
    )
    return {
        "id_alarma": a["id_alarma"],
        "tech_2g": a["tech_2g"],
        "tech_3g": a["tech_3g"],
        "tech_4g": a["tech_4g"],
        "fecha_creacion": a["fecha_creacion"],
        "municipio": a["municipio"],
        "departamento": a["departamento"],
        "notificada": a["notificada"],
        "duracion_horas": dur_h,
        "duracion_formateada": dur_fmt,
        "criticidad": criticidad,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    """Redirige al frontend si existe, o muestra info de la API."""
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {
        "mensaje": "API Sistema de Alarmas - Prueba Técnica Full Stack",
        "docs": "/docs",
        "endpoints": {
            "POST /api/importar": "Importar CSV de alarmas (separador |)",
            "GET  /api/alarmas": "Listar alarmas (?filtro=WARN|CRITICO|NORMAL)",
            "GET  /api/resumen-dia": "Resumen del día actual agrupado por hora",
            "GET  /api/exportar": "Exportar a Excel según filtro",
            "GET  /api/stats": "Estadísticas rápidas",
        },
    }


@app.post("/api/importar")
async def importar_csv(file: UploadFile = File(...)):
    """
    Importa un archivo CSV separado por '|'.
    Procesa cada fila, guarda en SQLite y aplica la lógica de criticidad.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="El archivo debe ser .csv")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    procesadas = []
    for row in reader:
        clean_row = {k.strip().strip('"'): v for k, v in row.items()}
        procesadas.append(procesar_fila(clean_row))

    guardar_alarmas(procesadas)

    # Conteo rápido de criticidad
    conteo = defaultdict(int)
    for a in procesadas:
        enriq = enriquecer_alarma(a)
        conteo[enriq["criticidad"]] += 1

    return {
        "mensaje": f"Importadas {len(procesadas)} alarmas correctamente",
        "total": len(procesadas),
        "por_criticidad": dict(conteo),
    }


@app.get("/api/alarmas", response_model=List[AlarmaResponse])
def listar_alarmas(
    filtro: Optional[str] = Query(
        None, description="Filtro: todos | WARN | CRITICO | NORMAL"
    ),
    municipio: Optional[str] = Query(None, description="Filtro parcial por municipio"),
    limit: Optional[int] = Query(None, description="Límite de registros (opcional)"),
):
    """
    Lista alarmas desde la base de datos.
    Recalcula duración y criticidad en cada llamada (tiempo real).
    """
    alarmas = cargar_alarmas_desde_db()
    resultado = []

    for a in alarmas:
        item = enriquecer_alarma(a)

        # Filtro de criticidad
        if filtro and filtro.upper() not in ("TODOS", ""):
            if item["criticidad"] != filtro.upper():
                continue

        # Filtro de municipio (búsqueda parcial, case-insensitive)
        if municipio and municipio.lower() not in item["municipio"].lower():
            continue

        resultado.append(item)

    if limit and limit > 0:
        resultado = resultado[:limit]

    return resultado


@app.get("/api/stats")
def estadisticas():
    """Devuelve conteos rápidos de criticidad."""
    alarmas = cargar_alarmas_desde_db()
    conteo = defaultdict(int)
    for a in alarmas:
        item = enriquecer_alarma(a)
        conteo[item["criticidad"]] += 1
    return {
        "total": len(alarmas),
        "por_criticidad": dict(conteo),
    }


@app.get("/api/resumen-dia")
def resumen_dia():
    """
    Módulo de Resumen del Día.
    Solo procesa alarmas cuya FECHA_CREACION corresponda al día actual.
    Agrupa por hora (00:00 – 23:00) y cuenta cuántas se crearon en cada franja.
    """
    hoy = datetime.now().date()
    por_hora = defaultdict(int)

    for a in cargar_alarmas_desde_db():
        fecha_dt = datetime.fromisoformat(a["fecha_creacion_dt"])
        if fecha_dt.date() == hoy:
            por_hora[fecha_dt.hour] += 1

    resumen = [{"hora": f"{h:02d}:00", "cantidad": por_hora.get(h, 0)} for h in range(24)]
    total_hoy = sum(por_hora.values())

    return {
        "fecha": hoy.isoformat(),
        "total_alarmas_hoy": total_hoy,
        "por_hora": resumen,
    }


@app.get("/api/exportar")
def exportar_excel(
    filtro: Optional[str] = Query(None, description="Filtro: todos | WARN | CRITICO | NORMAL"),
):
    """
    Exporta a Excel la información exacta que se está visualizando
    (respetando el filtro de criticidad aplicado).
    """
    datos = listar_alarmas(filtro=filtro)

    if not datos:
        raise HTTPException(status_code=404, detail="No hay datos para exportar")

    # Convertir a lista de dicts planos
    filas = [d.model_dump() if hasattr(d, "model_dump") else d for d in datos]
    df = pd.DataFrame(filas)
    df = df.rename(
        columns={
            "id_alarma": "ID_ALARMA",
            "tech_2g": "2G",
            "tech_3g": "3G",
            "tech_4g": "4G",
            "fecha_creacion": "FECHA_CREACION",
            "municipio": "MUNICIPIO",
            "departamento": "DEPARTAMENTO",
            "notificada": "NOTIFICADA",
            "duracion_horas": "DURACION_HORAS",
            "duracion_formateada": "DURACION",
            "criticidad": "CRITICIDAD",
        }
    )

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Alarmas")
    output.seek(0)

    filename = f"alarmas_{filtro or 'todos'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Arranque
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
