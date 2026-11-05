"""
DONPROFESOR (#Hack4Edu) · Punto de entrada del Servidor Web y Aplicación React (Persona 4).
Añade la carpeta backend/ a `sys.path`
para que `python backend/run.py` (o `pixi run start`) funcione desde cualquier directorio.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Garantizar que la raíz del proyecto esté en sys.path antes de importar `api` o `db`
ROOT_DIR = Path(__file__).resolve().parent  # backend/
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import uvicorn
from api.main import app

if __name__ == "__main__":
    print("Iniciando DONPROFESOR (React Frontend + FastAPI JWT + MCP DB Server) en http://localhost:8000 (0.0.0.0:8000) ...")
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)
