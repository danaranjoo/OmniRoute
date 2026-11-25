"""
Backend FastAPI para el sistema de gestión de alarmas.
Prueba técnica Full Stack - Desarrollador Python
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import pandas as pd
import io
import csv
from collections import defaultdict

app = FastAPI(
    title="Sistema de Alarmas - API",
    description="API REST para gestión, categorización y resumen de alarmas de red",
    version="1.0.0"
)

# CORS para frontend desacoplado
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Almacenamiento en memoria (para la prueba; en producción usar BD)
alarmas_db: List[Dict[str, Any]] = []


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
    criticidad: str  # "NORMAL", "WARN", "CRITICO"


def parse_fecha(fecha_str: str) -> datetime:
    """
    Parsea fechas del formato: 09-OCT-26 10.12.56.000000000 PM
    """
    # Limpiar el formato: reemplazar . por : en la hora y quitar nanosegundos
    # Ejemplo: 09-OCT-26 10.12.56.000000000 PM -> 09-OCT-26 10:12:56 PM
    try:
        parts = fecha_str.strip().split()
        if len(parts) >= 3:
            date_part = parts[0]  # 09-OCT-26
            time_part = parts[1]  # 10.12.56.000000000
            ampm = parts[2]       # PM

            # Tomar solo HH.MM.SS
            time_clean = ".".join(time_part.split(".")[:3])
            time_clean = time_clean.replace(".", ":")
            cleaned = f"{date_part} {time_clean} {ampm}"
            # Usar dateutil que maneja bien abreviaturas de mes en inglés
            return date_parser.parse(cleaned)
        else:
            return date_parser.parse(fecha_str)
    except Exception as e:
        # Fallback
        return datetime.now()


def calcular_duracion(fecha_creacion: datetime) -> tuple[float, str]:
    """Calcula la duración en horas desde fecha_creacion hasta ahora."""
    ahora = datetime.now()
    delta = ahora - fecha_creacion
    horas = delta.total_seconds() / 3600
    # Formato legible
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
    duracion_horas: float
) -> str:
    """
    LÓGICA DE NEGOCIO (programada SIN ayuda de IA - para sustentar en entrevista).
    
    Condiciones base (TODAS deben cumplirse):
    1. Disponibilidad de Tecnologías: 2G, 3G y 4G deben ser >= 0
    2. Capacidad al Límite: Al menos una de las tecnologías disponibles debe ser exactamente 100
    3. Estado de Notificación: NOTIFICADA == 'N'
    
    Niveles:
    - WARN: condiciones base + duración > 1h y <= 24h
    - CRITICO: condiciones base + duración > 24h
    - NORMAL: en cualquier otro caso
    """
    # 1. Validar valores >= 0
    if tech_2g < 0 or tech_3g < 0 or tech_4g < 0:
        return "NORMAL"

    # 2. Al menos una tecnología en 100
    if not (tech_2g == 100 or tech_3g == 100 or tech_4g == 100):
        return "NORMAL"

    # 3. No notificada
    if notificada.upper() != "N":
        return "NORMAL"

    # Niveles de alerta por tiempo
    if duracion_horas > 24:
        return "CRITICO"
    elif duracion_horas > 1:
        return "WARN"
    else:
        return "NORMAL"


def procesar_fila(row: Dict[str, str]) -> Dict[str, Any]:
    """Procesa una fila del CSV y aplica lógica de negocio."""
    try:
        tech_2g = int(row.get("2G", 0) or 0)
        tech_3g = int(row.get("3G", 0) or 0)
        tech_4g = int(row.get("4G", 0) or 0)
    except (ValueError, TypeError):
        tech_2g = tech_3g = tech_4g = 0

    fecha_str = row.get("FECHA_CREACION", "")
    fecha_dt = parse_fecha(fecha_str)
    duracion_h, duracion_fmt = calcular_duracion(fecha_dt)
    notificada = str(row.get("NOTIFICADA", "N")).strip()

    criticidad = aplicar_logica_criticidad(
        tech_2g, tech_3g, tech_4g, notificada, duracion_h
    )

    return {
        "id_alarma": str(row.get("ID_ALARMA", "")),
        "tech_2g": tech_2g,
        "tech_3g": tech_3g,
        "tech_4g": tech_4g,
        "fecha_creacion": fecha_str,
        "fecha_creacion_dt": fecha_dt.isoformat(),
        "municipio": row.get("MUNICIPIO", "").strip('"'),
        "departamento": row.get("DEPARTAMENTO", "").strip('"'),
        "notificada": notificada,
        "duracion_horas": duracion_h,
        "duracion_formateada": duracion_fmt,
        "criticidad": criticidad,
    }


@app.get("/")
def root():
    return {
        "mensaje": "API Sistema de Alarmas - Prueba Técnica Full Stack",
        "endpoints": {
            "POST /api/importar": "Importar CSV de alarmas",
            "GET /api/alarmas": "Listar alarmas (con filtro opcional)",
            "GET /api/resumen-dia": "Resumen del día actual agrupado por hora",
            "GET /api/exportar": "Exportar a Excel según filtro",
        }
    }


@app.post("/api/importar")
async def importar_csv(file: UploadFile = File(...)):
    """
    Importa un archivo CSV separado por '|'.
    Procesa cada fila, calcula duración y aplica lógica de criticidad.
    """
    global alarmas_db

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="El archivo debe ser .csv")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    # Leer CSV con separador |
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    procesadas = []
    for row in reader:
        # Limpiar claves (por si tienen comillas)
        clean_row = {k.strip().strip('"'): v for k, v in row.items()}
        procesadas.append(procesar_fila(clean_row))

    alarmas_db = procesadas

    # Contar por criticidad
    conteo = defaultdict(int)
    for a in alarmas_db:
        conteo[a["criticidad"]] += 1

    return {
        "mensaje": f"Importadas {len(alarmas_db)} alarmas correctamente",
        "total": len(alarmas_db),
        "por_criticidad": dict(conteo),
    }


@app.get("/api/alarmas", response_model=List[AlarmaResponse])
def listar_alarmas(
    filtro: Optional[str] = Query(
        None,
        description="Filtro: todos | WARN | CRITICO | NORMAL"
    )
):
    """
    Lista todas las alarmas o filtradas por criticidad.
    Recalcula duración en tiempo real.
    """
    resultado = []
    for a in alarmas_db:
        # Recalcular duración actual
        fecha_dt = datetime.fromisoformat(a["fecha_creacion_dt"])
        dur_h, dur_fmt = calcular_duracion(fecha_dt)
        criticidad = aplicar_logica_criticidad(
            a["tech_2g"], a["tech_3g"], a["tech_4g"],
            a["notificada"], dur_h
        )
        item = {
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
        if filtro is None or filtro.upper() == "TODOS" or filtro.upper() == criticidad:
            resultado.append(item)
    return resultado


@app.get("/api/resumen-dia")
def resumen_dia():
    """
    Módulo de Resumen del Día.
    Solo procesa alarmas cuya FECHA_CREACION sea el día actual.
    Agrupa por hora (0-23) y cuenta total de alarmas por franja.
    """
    hoy = datetime.now().date()
    por_hora = defaultdict(int)

    for a in alarmas_db:
        fecha_dt = datetime.fromisoformat(a["fecha_creacion_dt"])
        if fecha_dt.date() == hoy:
            hora = fecha_dt.hour
            por_hora[hora] += 1

    # Generar lista completa de 0 a 23
    resumen = []
    for h in range(24):
        resumen.append({
            "hora": f"{h:02d}:00",
            "cantidad": por_hora.get(h, 0)
        })

    total_hoy = sum(por_hora.values())
    return {
        "fecha": hoy.isoformat(),
        "total_alarmas_hoy": total_hoy,
        "por_hora": resumen
    }


@app.get("/api/exportar")
def exportar_excel(
    filtro: Optional[str] = Query(
        None,
        description="Filtro: todos | WARN | CRITICO | NORMAL"
    )
):
    """
    Exporta a Excel la información exacta que se está visualizando
    (respetando el filtro aplicado).
    """
    # Reutilizar lógica de listado
    datos = listar_alarmas(filtro=filtro)

    if not datos:
        raise HTTPException(status_code=404, detail="No hay datos para exportar")

    df = pd.DataFrame([d.model_dump() if hasattr(d, "model_dump") else d for d in datos])
    # Renombrar columnas amigables
    df = df.rename(columns={
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
    })

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Alarmas")
    output.seek(0)

    filename = f"alarmas_{filtro or 'todos'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
