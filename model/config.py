"""
DONPROFESOR · Configuración del flujo de predicción (sin valores "mágicos" repartidos por el código).

Todo lo ajustable se lee de variables de entorno, con valores por defecto documentados en .env.example.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def _float_env(nombre: str, defecto: float) -> float:
    try:
        return float(os.environ.get(nombre, defecto))
    except (TypeError, ValueError):
        return defecto


def model_path() -> Path:
    """Ruta del paquete de modelos de Carlos (salida de entrenadorModelo.py)."""
    ruta = os.environ.get("DONPROFESOR_MODEL_PATH", "").strip()
    if not ruta:
        return ROOT_DIR / "modelo.joblib"
    p = Path(ruta)
    return p if p.is_absolute() else ROOT_DIR / p


def umbral_alto() -> float:
    """Probabilidad a partir de la cual un riesgo se considera ALTO (0-1)."""
    return _float_env("DONPROFESOR_UMBRAL_RIESGO_ALTO", 0.5)


def umbral_medio() -> float:
    """Probabilidad a partir de la cual un riesgo se considera MEDIO (0-1)."""
    return _float_env("DONPROFESOR_UMBRAL_RIESGO_MEDIO", 0.2)


def desanimo_alto() -> float:
    """Índice de desánimo (escala 0-10 del modelo) a partir del cual es ALTO."""
    return _float_env("DONPROFESOR_DESANIMO_ALTO", 7.0)


def desanimo_medio() -> float:
    return _float_env("DONPROFESOR_DESANIMO_MEDIO", 5.0)


def k_minimo() -> int:
    """Tamaño mínimo de grupo para mostrar datos agregados (k-anonimato)."""
    try:
        return max(1, int(os.environ.get("DONPROFESOR_K_MINIMO", "5")))
    except ValueError:
        return 5


# Nota mínima aprobatoria de la escala vigesimal oficial de Perú (no es un parámetro del modelo)
NOTA_APROBATORIA = 11.0
