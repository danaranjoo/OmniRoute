# Sistema de Gestión de Alarmas — Prueba Técnica Full Stack

Aplicación **Full Stack desacoplada** para importar, categorizar por criticidad y visualizar alarmas de red.

**Repositorio:** https://github.com/danaranjoo/OmniRoute

---

## Stack

| Capa        | Tecnología                              |
|-------------|-----------------------------------------|
| Backend     | Python 3 + **FastAPI** + Uvicorn        |
| Persistencia| **SQLite** (archivo local)              |
| Frontend    | HTML5 + CSS3 + JavaScript Vanilla       |
| Datos       | Pandas + OpenPyXL (export Excel)        |
| Comunicación| **API REST** (JSON)                     |

> Frontend y Backend están **completamente desacoplados**.  
> El frontend solo consume endpoints REST.

---

## Cómo ejecutar

```bash
# 1. Backend
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Abre el navegador en:

- **App completa:** http://localhost:8000  
- **Swagger (docs):** http://localhost:8000/docs  

El backend también sirve el frontend automáticamente.

---

## Endpoints

| Método | Ruta                | Descripción                                          |
|--------|---------------------|------------------------------------------------------|
| POST   | `/api/importar`     | Sube CSV separado por `\|`                           |
| GET    | `/api/alarmas`      | Lista alarmas. Query: `filtro`, `municipio`, `limit` |
| GET    | `/api/stats`        | Conteos de criticidad                                |
| GET    | `/api/resumen-dia`  | Agregación del día actual por hora                   |
| GET    | `/api/exportar`     | Descarga Excel respetando el filtro activo           |

---

## Lógica de Negocio (Criticidad)

> **Esta función fue programada en su totalidad SIN ayuda de IA**  
> → `aplicar_logica_criticidad()` en `backend/main.py`

### Condiciones base (TODAS deben cumplirse)

1. **Disponibilidad de Tecnologías**  
   `2G >= 0` **y** `3G >= 0` **y** `4G >= 0`

2. **Capacidad al Límite**  
   Al menos **una** tecnología debe ser **exactamente 100**

3. **Estado de Notificación**  
   `NOTIFICADA == 'N'`

### Niveles según tiempo transcurrido

| Nivel       | Condición de tiempo                          |
|-------------|----------------------------------------------|
| **WARN**    | Condiciones base + duración **> 1 h y ≤ 24 h** |
| **CRÍTICO** | Condiciones base + duración **> 24 h**         |
| **NORMAL**  | Cualquier otro caso                          |

---

## Características de la interfaz

- Tabla con **duración acumulada** calculada en tiempo real
- Indicadores visuales (badge + borde de color) según criticidad
- Filtros: Todos / WARN / CRÍTICO / Normales
- Búsqueda por municipio (en tiempo real)
- Exportación a Excel de la vista filtrada
- Botón **Resumen del Día** → modal con barras hora a hora

---

## Estructura del proyecto

```
OmniRoute/
├── backend/
│   ├── main.py              # Toda la lógica de la API + lógica de negocio
│   ├── requirements.txt
│   └── alarmas.db           # Se crea automáticamente al importar
├── frontend/
│   └── index.html           # SPA completa
├── .gitignore
└── README.md
```

---

## Notas para la sustentación (entrevista)

1. **Servicio programado sin IA**  
   Función `aplicar_logica_criticidad`. Se puede abrir el archivo y explicar cada `if` línea por línea.

2. **Parseo de fechas**  
   El CSV trae `09-OCT-26 10.12.56.000000000 PM`.  
   Se normaliza y se usa `dateutil.parser`.

3. **Duración en tiempo real**  
   Cada vez que se lista (`/api/alarmas` o `/api/stats`) se recalcula  
   `ahora − fecha_creacion`.

4. **Persistencia**  
   SQLite simple. Al importar se hace un `DELETE` + `INSERT` de todos los registros.

5. **Resumen del día**  
   Filtra `fecha.date() == today` y agrupa con `defaultdict` por `hour`.

6. **Export Excel**  
   Reutiliza el mismo endpoint de listado (con filtro) y genera el `.xlsx` con pandas + openpyxl.

7. **Arquitectura desacoplada**  
   El frontend puede correr en otro puerto o dominio; solo necesita la URL del backend.

---

## Datos de prueba

Archivo de muestra: `Muestra de datos.csv` (~1499 registros, separador `|`).

Con ese archivo (fechas de sep-oct 2026) se obtienen principalmente registros **CRÍTICO**  
porque ya superan las 24 horas desde su creación.
