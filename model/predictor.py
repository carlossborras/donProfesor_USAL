"""
DONPROFESOR (#Hack4Edu 2026, Reto 13) · Predicciones con el modelo de Carlos (LightGBM + Random Forest).

Carga el paquete generado por `entrenadorModelo.py` (por defecto `modelo.joblib` en la raíz del repo,
configurable con DONPROFESOR_MODEL_PATH) y calcula, para cada estudiante, con los datos que se conocen
el día de la matrícula:

  Clasificación  -> probabilidad de abandono escolar, pérdida de beca (solo familias en Juntos) y
                    repetición; clase de necesidad de intervención (Alta / Media / Baja).
  Regresión      -> notas y faltas previstas de los 3 trimestres e índice de desánimo (0-10).
  Explicación    -> factores del propio estudiante que más empujan al alza la necesidad de intervención,
                    medidos con el propio modelo (se sustituye cada variable por su valor de referencia
                    del entrenamiento y se mide cuánto baja la predicción).

Si el modelo no se puede cargar se lanza ModelUnavailable con un mensaje claro: nunca se inventan
predicciones.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from model import config
from model.explicaciones import NO_EXPLICAR, SUGERENCIAS, texto_factor

log = logging.getLogger("donprofesor.predictor")

# Variables objetivo del paquete de Carlos -> columna en la base de datos
CLASIFICACION = {
    "abandono_escolar": "prob_abandono_pct",
    "perdida_beca": "prob_perdida_beca_pct",
    "repeticion": "prob_repeticion_pct",
}
NECESIDAD = "necesidad_intervencion"
REGRESION = {
    "nota_trimestre_1_0_20": ("prediccion_nota_t1", 0.0, 20.0),
    "nota_trimestre_2_0_20": ("prediccion_nota_t2", 0.0, 20.0),
    "nota_trimestre_3_real": ("prediccion_nota_t3", 0.0, 20.0),
    "faltas_trimestre_1": ("prediccion_faltas_t1", 0.0, None),
    "faltas_trimestre_2": ("prediccion_faltas_t2", 0.0, None),
    "ausencias_trimestre_3": ("prediccion_faltas_t3", 0.0, None),
    "desanimo_calculado": ("indice_desanimo", 0.0, 10.0),
}
PREDICTION_COLUMNS = (
    list(CLASIFICACION.values())
    + [NECESIDAD, "prob_necesidad_alta_pct"]
    + [v[0] for v in REGRESION.values()]
    + ["factor_principal_riesgo", "factores_json", "recomendacion_pedagogica", "modelo_version", "fecha_prediccion"]
)

# Especificación de entrada usada en entrenadorModelo.py (solo si no se puede leer del propio modelo)
_SPEC_POR_DEFECTO = {
    "num": ["distancia_hogar_escuela_km", "horas_trabajo_semanal", "dias_lectivos_previstos"],
    "cat": ["sexo", "zona_escuela", "ocupacion_madre", "ocupacion_padre",
            "tiempo_estudio_semanal", "tiempo_desplazamiento", "tamano_familia"],
    "bin": ["educacion_madre_0_4", "educacion_padre_0_4", "grado_secundaria", "edad",
            "repeticiones_previas", "internet_hogar", "apoyo_escolar", "apoyo_familiar", "beneficiario_juntos"],
}

_VERDADERO = {"1", "true", "si", "sí", "s", "yes", "y", "verdadero"}
_FALSO = {"0", "false", "no", "n", "falso"}


class ModelUnavailable(RuntimeError):
    """El modelo no se puede usar (falta el fichero, una librería o no es compatible)."""


@dataclass
class ModelBundle:
    modelos: Dict[str, Any]
    numericas: List[str]
    categoricas: List[str]
    binarias: List[str]
    categorias: Dict[str, List[str]] = field(default_factory=dict)
    referencia: Dict[str, Any] = field(default_factory=dict)
    importancias: Dict[str, float] = field(default_factory=dict)
    version: str = ""
    ruta: str = ""

    @property
    def variables(self) -> List[str]:
        return self.numericas + self.categoricas + self.binarias

    @property
    def objetivos(self) -> List[str]:
        return sorted(self.modelos)


_lock = threading.Lock()
_bundle: Optional[ModelBundle] = None
_ultimo_error: Optional[str] = None


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------

def _tipo_transformador(nombre: str, trans: Any) -> str:
    pasos = list(getattr(trans, "named_steps", {}).values()) or [trans]
    tipos = {type(p).__name__ for p in pasos}
    if "OneHotEncoder" in tipos or nombre == "cat":
        return "cat"
    if "StandardScaler" in tipos or nombre == "num":
        return "num"
    return "bin"


def _spec_desde_pipeline(pipe: Any) -> Dict[str, Any]:
    pasos = getattr(pipe, "named_steps", {})
    pre = pasos.get("preprocesamiento") or (pipe.steps[0][1] if hasattr(pipe, "steps") else None)
    spec = {"num": [], "cat": [], "bin": [], "categorias": {}, "referencia": {}}
    for nombre, trans, columnas in getattr(pre, "transformers_", []):
        if nombre == "remainder" or trans in ("drop", "passthrough"):
            continue
        columnas = list(columnas)
        tipo = _tipo_transformador(nombre, trans)
        spec[tipo] += columnas
        internos = getattr(trans, "named_steps", {})
        imputador = internos.get("imputar") if internos else trans
        stats = getattr(imputador, "statistics_", None)
        if stats is not None:
            spec["referencia"].update(dict(zip(columnas, list(stats))))
        onehot = internos.get("onehot") if internos else None
        if onehot is not None and hasattr(onehot, "categories_"):
            spec["categorias"].update({c: [str(x) for x in cats] for c, cats in zip(columnas, onehot.categories_)})
    return spec


def _importancias(paquete: Dict[str, Any], variables: Iterable[str]) -> Dict[str, float]:
    nombres, pesos = paquete.get("nombres_variables"), paquete.get("pesos_abandono")
    if nombres is None or pesos is None or len(nombres) != len(pesos):
        return {}
    agregadas: Dict[str, float] = {}
    for nombre, peso in zip(nombres, pesos):
        base = next((v for v in variables if nombre == v or str(nombre).startswith(v + "_")), str(nombre))
        agregadas[base] = agregadas.get(base, 0.0) + float(peso)
    return agregadas


def _cargar(ruta: Path) -> ModelBundle:
    if not ruta.exists():
        raise ModelUnavailable(f"No se encuentra el modelo en {ruta}. Define DONPROFESOR_MODEL_PATH o añade modelo.joblib.")
    try:
        import joblib
    except ImportError as exc:  # pragma: no cover
        raise ModelUnavailable("Falta la librería joblib (instala scikit-learn).") from exc
    try:
        paquete = joblib.load(ruta)
    except ModuleNotFoundError as exc:
        raise ModelUnavailable(f"Falta una librería del modelo: {exc.name}. Instálala (p. ej. lightgbm) y reinicia.") from exc
    except Exception as exc:
        raise ModelUnavailable(f"No se pudo leer el modelo ({type(exc).__name__}: {exc}).") from exc

    modelos = paquete.get("modelos") if isinstance(paquete, dict) and "modelos" in paquete else paquete
    if not isinstance(modelos, dict) or not modelos:
        raise ModelUnavailable("El fichero no tiene el formato esperado ({'modelos': {...}}) de entrenadorModelo.py.")

    referencia_pipe = modelos.get(NECESIDAD) or next(iter(modelos.values()))
    spec = _spec_desde_pipeline(referencia_pipe)
    if not (spec["num"] or spec["cat"] or spec["bin"]):
        spec.update({k: list(v) for k, v in _SPEC_POR_DEFECTO.items()})

    contenido = ruta.read_bytes()
    fecha = datetime.fromtimestamp(ruta.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d")
    version = f"{ruta.name} · {fecha} · {hashlib.sha1(contenido).hexdigest()[:8]}"
    variables = spec["num"] + spec["cat"] + spec["bin"]
    return ModelBundle(
        modelos=modelos,
        numericas=spec["num"],
        categoricas=spec["cat"],
        binarias=spec["bin"],
        categorias=spec["categorias"],
        referencia=spec["referencia"],
        importancias=_importancias(paquete if isinstance(paquete, dict) else {}, variables),
        version=version,
        ruta=str(ruta),
    )


def get_bundle(force_reload: bool = False) -> ModelBundle:
    """Devuelve el modelo cargado (se carga una vez y se reutiliza)."""
    global _bundle, _ultimo_error
    with _lock:
        if _bundle is None or force_reload:
            try:
                _bundle = _cargar(config.model_path())
                _ultimo_error = None
                log.info("Modelo cargado: %s", _bundle.version)
            except ModelUnavailable as exc:
                _bundle = None
                _ultimo_error = str(exc)
                raise
        return _bundle


def set_bundle_for_tests(bundle: Optional[ModelBundle]) -> None:
    """Permite inyectar un modelo en las pruebas automáticas."""
    global _bundle, _ultimo_error
    with _lock:
        _bundle, _ultimo_error = bundle, None


def model_status() -> Dict[str, Any]:
    try:
        b = get_bundle()
    except ModelUnavailable as exc:
        return {"disponible": False, "error": str(exc), "ruta": str(config.model_path())}
    return {
        "disponible": True,
        "version": b.version,
        "ruta": b.ruta,
        "variables": b.variables,
        "objetivos": b.objetivos,
        "umbrales": {
            "riesgo_alto": config.umbral_alto(),
            "riesgo_medio": config.umbral_medio(),
            "desanimo_alto": config.desanimo_alto(),
            "desanimo_medio": config.desanimo_medio(),
        },
    }


def input_fields() -> Dict[str, Any]:
    """Campos de entrada que necesita el modelo, con las categorías que aprendió (para formularios)."""
    b = get_bundle()
    return {
        "numericas": b.numericas,
        "categoricas": {c: b.categorias.get(c, []) for c in b.categoricas},
        "binarias": b.binarias,
        "version": b.version,
    }


# ---------------------------------------------------------------------------
# Preparación de datos
# ---------------------------------------------------------------------------

def _normaliza(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(sin_tildes.lower().split())


def _a_numero(valor: Any) -> float:
    if valor is None:
        return np.nan
    if isinstance(valor, (bool, np.bool_)):
        return 1.0 if valor else 0.0
    if isinstance(valor, str):
        t = valor.strip().lower()
        if t in _VERDADERO:
            return 1.0
        if t in _FALSO:
            return 0.0
        try:
            return float(t.replace(",", "."))
        except ValueError:
            return np.nan
    try:
        return float(valor)
    except (TypeError, ValueError):
        return np.nan


def _a_categoria(valor: Any, conocidas: List[str]) -> Any:
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return np.nan
    texto = str(valor).strip()
    if not texto:
        return np.nan
    if conocidas:
        mapa = {_normaliza(c): c for c in conocidas}
        return mapa.get(_normaliza(texto), texto)
    return texto


def build_frame(registros: List[Dict[str, Any]], bundle: ModelBundle) -> pd.DataFrame:
    """Construye la matriz de entrada con los nombres y tipos que espera el modelo."""
    filas = []
    for r in registros:
        fila = {}
        for c in bundle.numericas + bundle.binarias:
            fila[c] = _a_numero(r.get(c))
        for c in bundle.categoricas:
            fila[c] = _a_categoria(r.get(c), bundle.categorias.get(c, []))
        filas.append(fila)
    X = pd.DataFrame(filas, columns=bundle.variables)
    for c in bundle.categoricas:
        X[c] = X[c].astype(object)
    return X


def missing_fields(registro: Dict[str, Any], bundle: ModelBundle) -> List[str]:
    X = build_frame([registro], bundle)
    return [c for c in bundle.variables if pd.isna(X.iloc[0][c])]


# ---------------------------------------------------------------------------
# Predicción
# ---------------------------------------------------------------------------

def _indice_positivo(clases: Iterable[Any]) -> Optional[int]:
    for i, c in enumerate(clases):
        if c is True or str(c).strip().lower() in ("1", "1.0", "true", "si", "sí"):
            return i
    return None


def _proba_positiva(modelo: Any, X: pd.DataFrame) -> np.ndarray:
    proba = modelo.predict_proba(X)
    i = _indice_positivo(getattr(modelo, "classes_", []))
    if i is None:
        raise ModelUnavailable("Un clasificador binario del modelo no tiene clase positiva (1/True).")
    return proba[:, i]


def _puntuacion_revision(bundle: ModelBundle, X: pd.DataFrame) -> Optional[np.ndarray]:
    """Puntuación que se explica: P(necesidad Alta o Media); si no existe, P(abandono)."""
    modelo = bundle.modelos.get(NECESIDAD)
    if modelo is not None and hasattr(modelo, "predict_proba"):
        clases = [str(c) for c in getattr(modelo, "classes_", [])]
        proba = modelo.predict_proba(X)
        cols = [i for i, c in enumerate(clases) if c in ("Alta", "Media")]
        if cols:
            return proba[:, cols].sum(axis=1)
    if "abandono_escolar" in bundle.modelos:
        return _proba_positiva(bundle.modelos["abandono_escolar"], X)
    return None


def _explicar(bundle: ModelBundle, X: pd.DataFrame, max_factores: int = 3) -> List[List[Dict[str, Any]]]:
    base = _puntuacion_revision(bundle, X)
    vacio = [[] for _ in range(len(X))]
    if base is None:
        return vacio
    variables = [v for v in bundle.variables if v not in NO_EXPLICAR and v in bundle.referencia]
    if not variables:
        return vacio
    bloques = []
    for v in variables:
        Xv = X.copy()
        Xv[v] = bundle.referencia[v]
        bloques.append(Xv)
    sin_factor = _puntuacion_revision(bundle, pd.concat(bloques, ignore_index=True))
    deltas = base[None, :] - sin_factor.reshape(len(variables), len(X))  # [variable, alumno]

    resultado = []
    for j in range(len(X)):
        positivos = [(variables[i], float(deltas[i, j])) for i in range(len(variables)) if deltas[i, j] > 0.005]
        positivos.sort(key=lambda t: t[1], reverse=True)
        total = sum(d for _, d in positivos) or 1.0
        resultado.append([
            {
                "variable": v,
                "texto": texto_factor(v, X.iloc[j][v]),
                "peso_relativo": round(100.0 * d / total, 1),
                "sugerencia": SUGERENCIAS.get(v),
            }
            for v, d in positivos[:max_factores]
        ])
    return resultado


def _redondea(valor: float, minimo: Optional[float], maximo: Optional[float], decimales: int) -> float:
    if minimo is not None:
        valor = max(minimo, valor)
    if maximo is not None:
        valor = min(maximo, valor)
    return round(float(valor), decimales)


def predict_records(registros: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Predice para una lista de estudiantes (dicts con las variables de entrada). Lanza ModelUnavailable."""
    if not registros:
        return []
    bundle = get_bundle()
    X = build_frame(registros, bundle)
    n = len(X)
    salida: List[Dict[str, Any]] = [{} for _ in range(n)]
    try:
        for objetivo, columna in CLASIFICACION.items():
            modelo = bundle.modelos.get(objetivo)
            valores = _proba_positiva(modelo, X) if modelo is not None else [None] * n
            for i, v in enumerate(valores):
                salida[i][columna] = None if v is None else round(100.0 * float(v), 1)

        modelo = bundle.modelos.get(NECESIDAD)
        if modelo is not None:
            etiquetas = modelo.predict(X)
            clases = [str(c) for c in getattr(modelo, "classes_", [])]
            proba = modelo.predict_proba(X) if hasattr(modelo, "predict_proba") else None
            for i in range(n):
                salida[i][NECESIDAD] = str(etiquetas[i])
                if proba is not None and "Alta" in clases:
                    salida[i]["prob_necesidad_alta_pct"] = round(100.0 * float(proba[i, clases.index("Alta")]), 1)
                else:
                    salida[i]["prob_necesidad_alta_pct"] = None

        for objetivo, (columna, minimo, maximo) in REGRESION.items():
            modelo = bundle.modelos.get(objetivo)
            valores = modelo.predict(X) if modelo is not None else [None] * n
            decimales = 0 if columna.startswith("prediccion_faltas") else 1
            for i, v in enumerate(valores):
                salida[i][columna] = None if v is None else _redondea(v, minimo, maximo, decimales)

        explicaciones = _explicar(bundle, X)
    except ModelUnavailable:
        raise
    except Exception as exc:
        raise ModelUnavailable(f"El modelo falló al predecir ({type(exc).__name__}: {exc}).") from exc

    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    for i, r in enumerate(registros):
        # La pérdida de beca solo tiene sentido si la familia está en el programa Juntos
        if _a_numero(r.get("beneficiario_juntos")) != 1.0:
            salida[i]["prob_perdida_beca_pct"] = None
        factores = explicaciones[i]
        salida[i]["factores_json"] = factores
        salida[i]["factor_principal_riesgo"] = factores[0]["texto"] if factores else None
        sugerencias = [f["sugerencia"] for f in factores if f.get("sugerencia")]
        salida[i]["recomendacion_pedagogica"] = " ".join(dict.fromkeys(sugerencias)) or None
        salida[i]["modelo_version"] = bundle.version
        salida[i]["fecha_prediccion"] = ahora
    return salida


def nivel_probabilidad(pct: Optional[float]) -> Optional[str]:
    """Convierte una probabilidad (0-100) en nivel alto / medio / bajo según los umbrales configurados."""
    if pct is None:
        return None
    p = float(pct) / 100.0
    if p >= config.umbral_alto():
        return "alto"
    if p >= config.umbral_medio():
        return "medio"
    return "bajo"


def nivel_desanimo(valor: Optional[float]) -> Optional[str]:
    if valor is None:
        return None
    v = float(valor)
    if v >= config.desanimo_alto():
        return "alto"
    if v >= config.desanimo_medio():
        return "medio"
    return "bajo"
