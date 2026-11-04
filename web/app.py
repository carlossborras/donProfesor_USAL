"""
DONPROFESOR (#Hack4Edu) · Punto de entrada del Frontend y Servidor Web (Persona 4).
Sirve los 3 paneles interactivos (Docente, Dirección de Centro y Delegado Territorial)
junto con el Backend API JWT y el Chat conectado a la Base de Datos vía MCP.
"""

from __future__ import annotations
import uvicorn
from api.main import app

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
