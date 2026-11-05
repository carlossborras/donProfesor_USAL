"""
DONPROFESOR (#Hack4Edu 2026, Reto 13) · Alta e importación de estudiantes con predicción automática.

Flujo único que usan el formulario, el pegado desde Excel, la subida de CSV y la carga de la muestra:
  1. Normaliza cada fila (tipos, sí/no, campos vacíos) SIN inventar valores que falten.
  2. Aplica el ámbito de quien carga los datos (docente -> su grupo; director -> su escuela;
     delegado -> su UGEL) y rechaza estudiantes existentes de otro ámbito.
  3. Calcula las variables derivadas (faltas totales, asistencia, promedio) solo con datos reales.
  4. Ejecuta el modelo de Carlos (model/predictor.py) y guarda las predicciones. Si el modelo no está
     disponible, guarda los estudiantes con la predicción PENDIENTE y lo indica (no se inventa nada).
"""

from __future__ import annotations

import io
import json
import math
import uuid
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from db.adapter import db_adapter
from model import predictor

# Columnas que se pueden cargar desde fuera (todas las de entrada; las salidas del modelo se ignoran)
ENTEROS = {
    "edad", "grado_secundaria", "educacion_madre_0_4", "educacion_padre_0_4", "repeticiones_previas",
    "dias_lectivos_previstos", "faltas_trimestre_1", "faltas_trimestre_2",
}
SI_NO = {"internet_hogar", "apoyo_escolar", "apoyo_familiar", "beneficiario_juntos"}
DECIMALES = {"distancia_hogar_escuela_km", "horas_trabajo_semanal", "nota_trimestre_1_0_20", "nota_trimestre_2_0_20"}
TEXTOS = {
    "alumno_id", "escuela_id", "ugel", "distrito", "zona_escuela", "sexo", "tamano_familia",
    "ocupacion_madre", "ocupacion_padre", "tiempo_estudio_semanal", "tiempo_desplazamiento",
}
ENTRADA = ENTEROS | SI_NO | DECIMALES | TEXTOS
CALCULADAS = ["faltas_totales_calculadas", "asistencia_pct_calculada", "promedio_notas_calculado"]
COLUMNAS_GUARDADAS = sorted(ENTRADA) + CALCULADAS + ["docente_tutor"]

_VERDADERO = {"1", "1.0", "true", "si", "sí", "s", "yes", "verdadero"}
_FALSO = {"0", "0.0", "false", "no", "n", "falso"}
MAX_FILAS = 5000


class DatosInvalidos(ValueError):
    """Error de formato en los datos de entrada (se muestra tal cual a la persona usuaria)."""


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------

def _vacio(v: Any) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, str) and not v.strip())


def _entero(v: Any) -> Optional[int]:
    if _vacio(v):
        return None
    if isinstance(v, bool):
        return int(v)
    try:
        return int(round(float(str(v).replace(",", "."))))
    except ValueError:
        return None


def _decimal(v: Any) -> Optional[float]:
    if _vacio(v):
        return None
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def _si_no(v: Any) -> Optional[int]:
    if _vacio(v):
        return None
    if isinstance(v, bool):
        return int(v)
    t = str(v).strip().lower()
    if t in _VERDADERO:
        return 1
    if t in _FALSO:
        return 0
    return None


def normalizar(raw: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Devuelve (registro limpio, avisos de valores no válidos)."""
    reg: Dict[str, Any] = {}
    avisos: List[str] = []
    entrada = {str(k).strip().lower(): v for k, v in raw.items() if k is not None}
    for col in ENTRADA:
        v = entrada.get(col)
        if col in ENTEROS:
            reg[col] = _entero(v)
        elif col in SI_NO:
            reg[col] = _si_no(v)
        elif col in DECIMALES:
            reg[col] = _decimal(v)
        else:
            reg[col] = None if _vacio(v) else " ".join(str(v).split())
        if not _vacio(v) and reg[col] is None:
            avisos.append(f"{col}: valor no válido «{v}»")
    for col in ("nota_trimestre_1_0_20", "nota_trimestre_2_0_20"):
        if reg[col] is not None and not 0 <= reg[col] <= 20:
            avisos.append(f"{col}: debe estar entre 0 y 20")
            reg[col] = None
    if reg["grado_secundaria"] is not None and not 1 <= reg["grado_secundaria"] <= 5:
        avisos.append("grado_secundaria: debe estar entre 1 y 5")
        reg["grado_secundaria"] = None
    for col in ("escuela_id",):
        if reg[col]:
            reg[col] = reg[col].upper()
    return reg, avisos


def calcular_derivadas(reg: Dict[str, Any]) -> None:
    faltas = [reg.get("faltas_trimestre_1"), reg.get("faltas_trimestre_2")]
    conocidas = [f for f in faltas if f is not None]
    reg["faltas_totales_calculadas"] = sum(conocidas) if conocidas else None
    dias = reg.get("dias_lectivos_previstos")
    if conocidas and dias:
        reg["asistencia_pct_calculada"] = round(max(0.0, min(100.0, 100.0 * (dias - sum(conocidas)) / dias)), 2)
    else:
        reg["asistencia_pct_calculada"] = None
    notas = [n for n in (reg.get("nota_trimestre_1_0_20"), reg.get("nota_trimestre_2_0_20")) if n is not None]
    reg["promedio_notas_calculado"] = round(sum(notas) / len(notas), 2) if notas else None


# ---------------------------------------------------------------------------
# Ámbito
# ---------------------------------------------------------------------------

def where_ambito(user: Dict[str, Any], alias: str = "") -> Tuple[str, Tuple[Any, ...]]:
    """Filtro SQL (parametrizado, sin distinguir mayúsculas) del ámbito del usuario."""
    p = f"{alias}." if alias else ""
    rol = user.get("rol")
    if rol == "docente":
        return (f"UPPER(TRIM({p}escuela_id)) = UPPER(TRIM(?)) AND {p}grado_secundaria = ?",
                (user.get("escuela_id") or "", int(user.get("grado_secundaria") or 0)))
    if rol == "director":
        return f"UPPER(TRIM({p}escuela_id)) = UPPER(TRIM(?))", (user.get("escuela_id") or "",)
    if rol == "delegado":
        return f"UPPER(TRIM({p}ugel)) = UPPER(TRIM(?))", (user.get("ugel") or "",)
    return "1 = 0", ()


def _aplicar_ambito(reg: Dict[str, Any], user: Dict[str, Any]) -> Optional[str]:
    """Fija los campos de ámbito según quien carga. Devuelve un motivo de rechazo o None."""
    rol = user.get("rol")
    if rol == "docente":
        if not user.get("escuela_id") or not user.get("grado_secundaria"):
            return "Tu cuenta no tiene escuela o grado asignados."
        reg["escuela_id"] = str(user["escuela_id"]).upper()
        reg["grado_secundaria"] = int(user["grado_secundaria"])
        reg["docente_tutor"] = user.get("username") or user.get("sub")
        reg["ugel"] = reg.get("ugel") or user.get("ugel")
    elif rol == "director":
        if not user.get("escuela_id"):
            return "Tu cuenta no tiene escuela asignada."
        reg["escuela_id"] = str(user["escuela_id"]).upper()
        reg["ugel"] = reg.get("ugel") or user.get("ugel")
        reg["docente_tutor"] = None
    elif rol == "delegado":
        if not user.get("ugel"):
            return "Tu cuenta no tiene UGEL asignada."
        if reg.get("ugel") and reg["ugel"].strip().upper() != str(user["ugel"]).strip().upper():
            return f"La UGEL del estudiante ({reg['ugel']}) no es la tuya."
        reg["ugel"] = reg.get("ugel") or user["ugel"]
        reg["docente_tutor"] = None
    else:
        return "Rol no válido."
    if not reg.get("escuela_id"):
        return "Falta escuela_id."
    if not reg.get("grado_secundaria"):
        return "Falta grado_secundaria (1 a 5)."
    return None


def _en_ambito(fila: Dict[str, Any], user: Dict[str, Any]) -> bool:
    rol = user.get("rol")
    escuela = str(fila.get("escuela_id") or "").strip().upper()
    if rol == "docente":
        return escuela == str(user.get("escuela_id") or "").strip().upper() and \
            int(fila.get("grado_secundaria") or 0) == int(user.get("grado_secundaria") or -1)
    if rol == "director":
        return escuela == str(user.get("escuela_id") or "").strip().upper()
    if rol == "delegado":
        return str(fila.get("ugel") or "").strip().upper() == str(user.get("ugel") or "").strip().upper()
    return False


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------

def _existentes(ids: List[str]) -> Dict[str, Dict[str, Any]]:
    encontrados: Dict[str, Dict[str, Any]] = {}
    for i in range(0, len(ids), 500):
        bloque = ids[i:i + 500]
        filas = db_adapter.fetch_all(
            f"SELECT alumno_id, escuela_id, ugel, grado_secundaria FROM alumnos_hack4edu "
            f"WHERE alumno_id IN ({', '.join('?' * len(bloque))});",
            tuple(bloque),
        )
        encontrados.update({f["alumno_id"]: f for f in filas})
    return encontrados


def _upsert(reg: Dict[str, Any]) -> None:
    columnas = ["alumno_id"] + [c for c in COLUMNAS_GUARDADAS if c != "alumno_id"]
    actualizar = ", ".join(f"{c} = excluded.{c}" for c in columnas if c != "alumno_id")
    db_adapter.execute_write(
        f"INSERT INTO alumnos_hack4edu ({', '.join(columnas)}) VALUES ({', '.join('?' * len(columnas))}) "
        f"ON CONFLICT(alumno_id) DO UPDATE SET {actualizar};",
        tuple(reg.get(c) for c in columnas),
    )


def _guardar_predicciones(ids: List[str], predicciones: List[Dict[str, Any]]) -> None:
    columnas = predictor.PREDICTION_COLUMNS
    sets = ", ".join(f"{c} = ?" for c in columnas)
    for alumno_id, pred in zip(ids, predicciones):
        valores = []
        for c in columnas:
            v = pred.get(c)
            valores.append(json.dumps(v, ensure_ascii=False) if c == "factores_json" else v)
        db_adapter.execute_write(f"UPDATE alumnos_hack4edu SET {sets} WHERE alumno_id = ?;", tuple(valores) + (alumno_id,))


def _borrar_predicciones(ids: List[str]) -> None:
    sets = ", ".join(f"{c} = NULL" for c in predictor.PREDICTION_COLUMNS)
    for alumno_id in ids:
        db_adapter.execute_write(f"UPDATE alumnos_hack4edu SET {sets} WHERE alumno_id = ?;", (alumno_id,))


def _predecir_y_guardar(registros: List[Dict[str, Any]], borrar_si_falla: bool = True) -> Dict[str, Any]:
    if not registros:
        return {"calculadas": 0, "pendientes": 0, "aviso": None}
    ids = [r["alumno_id"] for r in registros]
    try:
        predicciones = predictor.predict_records(registros)
    except predictor.ModelUnavailable as exc:
        if borrar_si_falla:
            _borrar_predicciones(ids)  # nunca dejar predicciones antiguas con datos nuevos
        return {"calculadas": 0, "pendientes": len(ids), "aviso": f"Predicciones pendientes: {exc}"}
    _guardar_predicciones(ids, predicciones)
    return {"calculadas": len(ids), "pendientes": 0, "aviso": None}


def guardar_alumnos(filas: Iterable[Dict[str, Any]], user: Dict[str, Any], *, generar_id: bool = False) -> Dict[str, Any]:
    """Valida, guarda y predice. Devuelve un resumen para mostrar a la persona usuaria."""
    filas = list(filas)
    if not filas:
        raise DatosInvalidos("No hay estudiantes en los datos recibidos.")
    if len(filas) > MAX_FILAS:
        raise DatosInvalidos(f"Demasiadas filas ({len(filas)}). El máximo por carga es {MAX_FILAS}.")

    validos: List[Dict[str, Any]] = []
    rechazados: List[Dict[str, Any]] = []
    avisos: List[Dict[str, Any]] = []
    vistos = set()
    for n, raw in enumerate(filas, start=1):
        reg, problemas = normalizar(raw)
        if not reg.get("alumno_id"):
            if generar_id:
                reg["alumno_id"] = f"ALU-{uuid.uuid4().hex[:8].upper()}"
            else:
                rechazados.append({"fila": n, "alumno_id": None, "motivo": "Falta alumno_id."})
                continue
        motivo = _aplicar_ambito(reg, user)
        if motivo:
            rechazados.append({"fila": n, "alumno_id": reg["alumno_id"], "motivo": motivo})
            continue
        if reg["alumno_id"] in vistos:
            rechazados.append({"fila": n, "alumno_id": reg["alumno_id"], "motivo": "alumno_id repetido en la carga."})
            continue
        vistos.add(reg["alumno_id"])
        calcular_derivadas(reg)
        if problemas:
            avisos.append({"fila": n, "alumno_id": reg["alumno_id"], "avisos": problemas})
        validos.append(reg)

    existentes = _existentes([r["alumno_id"] for r in validos])
    guardables = []
    for reg in validos:
        previo = existentes.get(reg["alumno_id"])
        if previo and not _en_ambito(previo, user):
            rechazados.append({"fila": None, "alumno_id": reg["alumno_id"],
                               "motivo": "Ya existe un estudiante con ese código fuera de tu ámbito."})
            continue
        guardables.append(reg)

    for reg in guardables:
        _upsert(reg)
    prediccion = _predecir_y_guardar(guardables)

    incompletos = 0
    try:
        bundle = predictor.get_bundle()
        incompletos = sum(1 for r in guardables if predictor.missing_fields(r, bundle))
    except predictor.ModelUnavailable:
        pass

    creados = sum(1 for r in guardables if r["alumno_id"] not in existentes)
    return {
        "status": "ok" if guardables else "sin_cambios",
        "creados": creados,
        "actualizados": len(guardables) - creados,
        "rechazados": rechazados,
        "avisos": avisos,
        "datos_incompletos": incompletos,
        "predicciones": prediccion,
        "alumno_ids": [r["alumno_id"] for r in guardables],
    }


def recalcular(user: Dict[str, Any], solo_pendientes: bool = False) -> Dict[str, Any]:
    """Vuelve a predecir a los estudiantes del ámbito (p. ej. tras actualizar el modelo)."""
    where, params = where_ambito(user)
    extra = " AND necesidad_intervencion IS NULL" if solo_pendientes else ""
    filas = db_adapter.fetch_all(
        f"SELECT {', '.join(['alumno_id'] + sorted(ENTRADA - {'alumno_id'}))} FROM alumnos_hack4edu WHERE {where}{extra};",
        params,
    )
    # si el modelo falla al recalcular, los datos no han cambiado: se conservan las predicciones previas
    resultado = _predecir_y_guardar(filas, borrar_si_falla=False)
    resultado["total"] = len(filas)
    return resultado


def vaciar_ambito(user: Dict[str, Any]) -> int:
    where, params = where_ambito(user)
    fila = db_adapter.fetch_one(f"SELECT COUNT(*) AS n FROM alumnos_hack4edu WHERE {where};", params) or {}
    db_adapter.execute_write(f"DELETE FROM alumnos_hack4edu WHERE {where};", params)
    return int(fila.get("n") or 0)


# ---------------------------------------------------------------------------
# Lectura de ficheros / texto pegado
# ---------------------------------------------------------------------------

def leer_tabla(contenido: bytes | str) -> List[Dict[str, Any]]:
    """Lee CSV/TSV/«;» (o lo pegado desde Excel) como texto, sin que pandas cambie los tipos."""
    if isinstance(contenido, bytes):
        texto = None
        for codificacion in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                texto = contenido.decode(codificacion)
                break
            except UnicodeDecodeError:
                continue
    else:
        texto = contenido
    texto = (texto or "").strip()
    if not texto:
        raise DatosInvalidos("El fichero o el texto está vacío.")
    primera = texto.splitlines()[0]
    separador = max(["\t", ";", ","], key=primera.count)
    try:
        df = pd.read_csv(io.StringIO(texto), sep=separador, dtype=str, keep_default_na=False)
    except Exception as exc:
        raise DatosInvalidos(f"No se pudo leer la tabla: {exc}") from exc
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "alumno_id" not in df.columns:
        raise DatosInvalidos("La tabla debe tener una cabecera con la columna alumno_id.")
    return df.to_dict(orient="records")
