"""
Punto de entrada principal del proyecto.
Ejecutar desde la raíz:

    python main.py
"""

import sys
import os
from pathlib import Path

# Agregar la carpeta backend al path
BACKEND_DIR = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Cambiar el directorio de trabajo al backend (para que SQLite y frontend funcionen bien)
os.chdir(BACKEND_DIR)

if __name__ == "__main__":
    import uvicorn
    from main import app   # importa el app de backend/main.py

    print("=" * 50)
    print("  Sistema de Gestión de Alarmas")
    print("  http://localhost:8000")
    print("  Docs: http://localhost:8000/docs")
    print("=" * 50)

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
