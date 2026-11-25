# Sistema de Gestión de Alarmas - Prueba Técnica Full Stack

Aplicación Full Stack desacoplada para la gestión, categorización por criticidad y visualización de alarmas de red.

## Stack Tecnológico

| Capa       | Tecnología                          |
|------------|-------------------------------------|
| Backend    | **Python 3** + FastAPI + Uvicorn    |
| Frontend   | HTML5 + CSS3 + JavaScript Vanilla   |
| Datos      | Pandas + OpenPyXL (export Excel)    |
| Comunicación | API REST (JSON)                   |

> **Arquitectura completamente desacoplada**: el frontend solo consume endpoints REST. No hay templates del lado del servidor.

---

## Cómo ejecutar

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

La API quedará disponible en: http://localhost:8000  
Documentación interactiva (Swagger): http://localhost:8000/docs

### 2. Frontend

Simplemente abre el archivo `frontend/index.html` en el navegador  
**o** sirve la carpeta con cualquier servidor estático:

```bash
cd frontend
python -m http.server 5500
```

Luego ve a http://localhost:5500

---

## Endpoints de la API

| Método | Ruta                  | Descripción                                      |
|--------|-----------------------|--------------------------------------------------|
| POST   | `/api/importar`       | Sube un CSV separado por `\|`                    |
| GET    | `/api/alarmas`        | Lista alarmas. Query: `?filtro=WARN\|CRITICO\|NORMAL\|todos` |
| GET    | `/api/resumen-dia`    | Agregación del día actual por hora               |
| GET    | `/api/exportar`       | Descarga Excel respetando el filtro activo       |

---

## Lógica de Negocio (Criticidad)

> **Este servicio fue programado en su totalidad SIN ayuda de IA**  
> (función `aplicar_logica_criticidad` en `backend/main.py`)

### Condiciones base (deben cumplirse TODAS):

1. **Disponibilidad de Tecnologías**: los campos `2G`, `3G` y `4G` deben ser **≥ 0**.
2. **Capacidad al Límite**: **al menos una** de las tecnologías debe tener valor **exactamente 100**.
3. **Estado de Notificación**: `NOTIFICADA = 'N'`.

### Niveles de alerta (según duración desde `FECHA_CREACION`):

| Nivel     | Condición de tiempo                  |
|-----------|--------------------------------------|
| **WARN**  | Condiciones base + duración **> 1 h y ≤ 24 h** |
| **CRÍTICO** | Condiciones base + duración **> 24 h** |
| **NORMAL** | Cualquier otro caso                  |

---

## Características de la interfaz

- ✅ Tabla con **duración acumulada** calculada en tiempo real
- ✅ Indicadores visuales (badge + borde de color) según criticidad
- ✅ Filtros: Todos / WARN / CRÍTICO / Normales
- ✅ Exportación a Excel de la vista filtrada actual
- ✅ Botón **Resumen del Día**: modal con gráfico de barras hora a hora (solo alarmas del día actual)

---

## Estructura del proyecto

```
alarmas-app/
├── backend/
│   ├── main.py              # Toda la lógica de la API
│   └── requirements.txt
├── frontend/
│   └── index.html           # SPA completa (HTML + CSS + JS)
└── README.md
```

---

## Notas para la sustentación

1. **Servicio programado sin IA**: `aplicar_logica_criticidad()`.  
   Se puede demostrar leyendo el código y explicando cada `if`.

2. **Parseo de fechas**: el CSV trae formato `09-OCT-26 10.12.56.000000000 PM`.  
   Se normaliza a `09-OCT-26 10:12:56 PM` y se usa `dateutil.parser`.

3. **Duración en tiempo real**: cada vez que se lista, se recalcula `ahora - fecha_creacion`.

4. **Resumen del día**: filtra por `fecha.date() == today` y agrupa con `defaultdict` por `hour`.

5. **Export Excel**: se reutiliza el mismo endpoint de listado (con filtro) y se genera el `.xlsx` con pandas + openpyxl.

---

## Datos de prueba

El archivo de muestra se encuentra en la carpeta de adjuntos de la prueba:  
`Muestra de datos.csv` (≈ 1500 registros, separador `|`).
