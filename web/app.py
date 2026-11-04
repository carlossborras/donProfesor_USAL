"""
DONPROFESOR (#Hack4Edu) · Punto de entrada del Servidor Web y Aplicación React (Persona 4).
Soluciona la resolución de módulos añadiendo automáticamente la raíz del repositorio a `sys.path`
para que `uv run python web/app.py` o `python web/app.py` funcione desde cualquier directorio.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Garantizar que la raíz del proyecto esté en sys.path antes de importar `api` o `db`
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import uvicorn
from api.main import app

if __name__ == "__main__":
    print("Iniciando DONPROFESOR (React Frontend + FastAPI JWT + MCP DB Server) en http://localhost:8000 ...")
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)
