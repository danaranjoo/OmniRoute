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
# 1. Crear entorno virtual e instalar dependencias
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..

# 2. Ejecutar (forma más simple)
python main.py
```

Abre el navegador en:

- **App completa:** http://localhost:8000  
- **Swagger (docs):** http://localhost:8000/docs  

También puedes ejecutar desde dentro de `backend/`:

```bash
cd backend
python main.py
# o
uvicorn main:app --reload --port 8000
```

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
├── main.py                 # ← Ejecutar con: python main.py
├── backend/
│   ├── main.py              # Lógica de la API + lógica de negocio
│   ├── requirements.txt
│   └── alarmas.db           # Se crea automáticamente al importar
├── frontend/
│   └── index.html           # SPA completa
├── .gitignore
└── README.md
```

---

## Datos de prueba

Archivo de muestra: `Muestra de datos.csv` (~1499 registros, separador `|`).

Con ese archivo (fechas de sep-oct 2026) se obtienen principalmente registros **CRÍTICO**  
porque ya superan las 24 horas desde su creación.
