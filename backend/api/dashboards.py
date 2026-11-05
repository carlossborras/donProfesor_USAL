"""
DONPROFESOR (#Hack4Edu 2026, Reto 13) · Paneles con gráficos por rol.

  GET /api/dashboard          -> panel del rol de la sesión (el ámbito sale SIEMPRE del token)
  GET /api/dashboard/{rol}    -> igual, pero devuelve 403 si {rol} no es el de la sesión

Principios éticos aplicados en el servidor (no solo en la interfaz):
  - Docente: ve a su grupo alumno a alumno con factores explicados y «sugerir revisión».
    NO recibe probabilidades, etiquetas de riesgo ni predicciones numéricas. Sin rankings
    (los alumnos se ordenan por código).
  - Director y delegado: solo datos agregados. Cualquier grupo con menos de K_MIN alumnos se oculta.
  - Consultas siempre parametrizadas y filtradas por el ámbito del token.
  - Si la base de datos está vacía, el panel devuelve ceros y listas vacías (nunca datos inventados).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from api.security import ROLES, get_current_user
from db.adapter import db_adapter
from db.students import where_ambito
from model import config as model_config
import json

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

import os

K_MIN = model_config.k_minimo()
NOTA_APROBATORIA = float(model_config.NOTA_APROBATORIA)
UMBRAL_CONECTIVIDAD_PCT = float(os.environ.get("DONPROFESOR_UMBRAL_CONECTIVIDAD_PCT", "50"))
UMBRAL_DISTANCIA_KM = float(os.environ.get("DONPROFESOR_DISTANCIA_TRANSPORTE_KM", "3"))
SUGERIR_REVISION_SQL = "necesidad_intervencion IN ('Alta', 'Media')"

AVISO_DOCENTE = (
    "«Sugerir revisión» es una ayuda para priorizar tu atención, no un diagnóstico. "
    "Tú conoces a tu grupo y tú decides."
)
AVISO_AGREGADO = (
    f"Datos agregados. Los grupos con menos de {K_MIN} estudiantes se ocultan para proteger su privacidad."
)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _num(v: Any, dec: int = 1) -> Optional[float]:
    return None if v is None else round(float(v), dec)


def _ent(v: Any) -> int:
    return int(v or 0)


def _pct(parte: Any, total: Any) -> Optional[float]:
    total = _ent(total)
    return None if total == 0 else round(100.0 * _ent(parte) / total, 1)


def _kpi(kid: str, label: str, value: Any, unit: str = "", note: str = "") -> Dict[str, Any]:
    return {"id": kid, "label": label, "value": value, "unit": unit, "note": note}


def _base(rol: str, scope: Dict[str, Any], aviso: str) -> Dict[str, Any]:
    return {
        "rol": rol,
        "scope": scope,
        "k_minimo": K_MIN,
        "nota_aprobatoria": NOTA_APROBATORIA,
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hay_datos": False,
        "mensaje": None,
        "aviso": aviso,
        "kpis": [],
        "charts": {},
        "tablas": {},
    }


# ---------------------------------------------------------------------------
# Docente: su grupo (escuela + grado)
# ---------------------------------------------------------------------------

def _factores(fila: Dict[str, Any]) -> List[str]:
    factores: List[str] = []
    try:
        explicados = json.loads(fila.get("factores_json") or "[]")
    except ValueError:
        explicados = []
    factores.extend(str(f["texto"]) for f in explicados if isinstance(f, dict) and f.get("texto"))
    if not factores and fila.get("factor_principal_riesgo"):
        factores.append(str(fila["factor_principal_riesgo"]))
    horas = float(fila.get("horas_trabajo_semanal") or 0)
    if horas > 0:
        factores.append(f"Trabaja fuera del horario escolar (~{horas:g} h/semana)")
    distancia = float(fila.get("distancia_hogar_escuela_km") or 0)
    if distancia > UMBRAL_DISTANCIA_KM:
        factores.append(f"Vive a {distancia:g} km de la escuela")
    if fila.get("internet_hogar") == 0:
        factores.append("Sin internet en casa")
    faltas1, faltas2 = fila.get("faltas_trimestre_1"), fila.get("faltas_trimestre_2")
    if faltas1 is not None and faltas2 is not None and int(faltas2) > int(faltas1) + 3:
        factores.append(f"Sus faltas subieron en el 2.º trimestre ({faltas1} → {faltas2})")
    return factores


def panel_docente(user: Dict[str, Any]) -> Dict[str, Any]:
    escuela, grado = user.get("escuela_id"), user.get("grado_secundaria")
    datos = _base("docente", {"escuela_id": escuela, "grado_secundaria": grado}, AVISO_DOCENTE)
    if not escuela or not grado:
        datos["mensaje"] = "Tu cuenta no tiene escuela o grado asignados."
        return datos

    where, params = where_ambito(user)
    k = db_adapter.fetch_one(
        f"""
        SELECT COUNT(*) AS n,
               AVG(asistencia_pct_calculada) AS asistencia,
               AVG(nota_trimestre_1_0_20) AS t1,
               AVG(nota_trimestre_2_0_20) AS t2,
               AVG(promedio_notas_calculado) AS promedio,
               AVG(faltas_trimestre_1) AS faltas_t1,
               AVG(faltas_trimestre_2) AS faltas_t2,
               SUM(CASE WHEN promedio_notas_calculado >= {NOTA_APROBATORIA} THEN 1 ELSE 0 END) AS aprobados,
               SUM(CASE WHEN internet_hogar = 1 THEN 1 ELSE 0 END) AS con_internet,
               SUM(CASE WHEN internet_hogar = 0 THEN 1 ELSE 0 END) AS sin_internet,
               SUM(CASE WHEN {SUGERIR_REVISION_SQL} THEN 1 ELSE 0 END) AS revision,
               SUM(CASE WHEN horas_trabajo_semanal > 0 THEN 1 ELSE 0 END) AS trabaja,
               SUM(CASE WHEN distancia_hogar_escuela_km > {UMBRAL_DISTANCIA_KM} THEN 1 ELSE 0 END) AS lejos,
               SUM(CASE WHEN beneficiario_juntos = 1 THEN 1 ELSE 0 END) AS juntos,
               SUM(CASE WHEN asistencia_pct_calculada < 70 THEN 1 ELSE 0 END) AS a_70,
               SUM(CASE WHEN asistencia_pct_calculada >= 70 AND asistencia_pct_calculada < 80 THEN 1 ELSE 0 END) AS a_80,
               SUM(CASE WHEN asistencia_pct_calculada >= 80 AND asistencia_pct_calculada < 90 THEN 1 ELSE 0 END) AS a_90,
               SUM(CASE WHEN asistencia_pct_calculada >= 90 THEN 1 ELSE 0 END) AS a_100,
               SUM(CASE WHEN promedio_notas_calculado < 11 THEN 1 ELSE 0 END) AS n_11,
               SUM(CASE WHEN promedio_notas_calculado >= 11 AND promedio_notas_calculado < 14 THEN 1 ELSE 0 END) AS n_14,
               SUM(CASE WHEN promedio_notas_calculado >= 14 AND promedio_notas_calculado < 17 THEN 1 ELSE 0 END) AS n_17,
               SUM(CASE WHEN promedio_notas_calculado >= 17 THEN 1 ELSE 0 END) AS n_20
        FROM alumnos_hack4edu
        WHERE {where};
        """,
        params,
    ) or {}
    n = _ent(k.get("n"))
    datos["kpis"] = [
        _kpi("alumnos", "Estudiantes en tu grupo", n),
        _kpi("asistencia", "Asistencia media", _num(k.get("asistencia")), "%"),
        _kpi("nota_t2", "Nota media 2.º trimestre", _num(k.get("t2")), "/20",
             f"1.er trimestre: {_num(k.get('t1')) if n else '—'}"),
        _kpi("aprobados", "Con promedio aprobatorio (≥ 11)", _pct(k.get("aprobados"), n), "%"),
        _kpi("internet", "Con internet en casa", _pct(k.get("con_internet"), n), "%"),
        _kpi("revision", "Sugerencias de revisión", _ent(k.get("revision")), "",
             "Para tu criterio; no es una etiqueta"),
    ]
    if n == 0:
        datos["mensaje"] = "Todavía no hay estudiantes cargados para tu grupo."
        return datos

    filas = db_adapter.fetch_all(
        f"""
        SELECT alumno_id, asistencia_pct_calculada, faltas_trimestre_1, faltas_trimestre_2,
               nota_trimestre_1_0_20, nota_trimestre_2_0_20, promedio_notas_calculado,
               distancia_hogar_escuela_km, horas_trabajo_semanal, internet_hogar, beneficiario_juntos,
               necesidad_intervencion, factor_principal_riesgo, factores_json, recomendacion_pedagogica
        FROM alumnos_hack4edu
        WHERE {where}
        ORDER BY alumno_id ASC
        LIMIT 300;
        """,
        params,
    )
    alumnos = []
    for f in filas:
        sugerir = f.get("necesidad_intervencion") in ("Alta", "Media")
        alumnos.append({
            "alumno_id": f["alumno_id"],
            "asistencia_pct": _num(f.get("asistencia_pct_calculada")),
            "faltas_t1": _num(f.get("faltas_trimestre_1"), 0),
            "faltas_t2": _num(f.get("faltas_trimestre_2"), 0),
            "nota_t1": _num(f.get("nota_trimestre_1_0_20")),
            "nota_t2": _num(f.get("nota_trimestre_2_0_20")),
            "promedio": _num(f.get("promedio_notas_calculado")),
            "sugerir_revision": sugerir,
            "factores": _factores(f) if sugerir else [],
            "recomendacion": f.get("recomendacion_pedagogica") if sugerir else None,
        })

    datos["hay_datos"] = True
    datos["charts"] = {
        "notas_por_trimestre": [
            {"label": "1.er trimestre", "value": _num(k.get("t1"))},
            {"label": "2.º trimestre", "value": _num(k.get("t2"))},
        ],
        "faltas_por_trimestre": [
            {"label": "1.er trimestre", "value": _num(k.get("faltas_t1"))},
            {"label": "2.º trimestre", "value": _num(k.get("faltas_t2"))},
        ],
        "distribucion_asistencia": [
            {"label": "< 70 %", "value": _ent(k.get("a_70"))},
            {"label": "70–79 %", "value": _ent(k.get("a_80"))},
            {"label": "80–89 %", "value": _ent(k.get("a_90"))},
            {"label": "≥ 90 %", "value": _ent(k.get("a_100"))},
        ],
        "distribucion_notas": [
            {"label": "< 11", "value": _ent(k.get("n_11"))},
            {"label": "11–13", "value": _ent(k.get("n_14"))},
            {"label": "14–16", "value": _ent(k.get("n_17"))},
            {"label": "17–20", "value": _ent(k.get("n_20"))},
        ],
        "asistencia_vs_distancia": [
            {"x": _num(f.get("distancia_hogar_escuela_km"), 2), "y": _num(f.get("asistencia_pct_calculada"))}
            for f in filas
            if f.get("distancia_hogar_escuela_km") is not None and f.get("asistencia_pct_calculada") is not None
        ],
        "contexto": [
            {"label": "Trabaja fuera del horario escolar", "value": _ent(k.get("trabaja"))},
            {"label": f"Vive a más de {UMBRAL_DISTANCIA_KM:g} km", "value": _ent(k.get("lejos"))},
            {"label": "Sin internet en casa", "value": _ent(k.get("sin_internet"))},
            {"label": "Familia en el programa Juntos", "value": _ent(k.get("juntos"))},
        ],
    }
    datos["tablas"] = {"alumnos": alumnos}
    return datos


# ---------------------------------------------------------------------------
# Director: su escuela, agregada por grado (k >= K_MIN)
# ---------------------------------------------------------------------------

def panel_director(user: Dict[str, Any]) -> Dict[str, Any]:
    escuela = user.get("escuela_id")
    datos = _base("director", {"escuela_id": escuela}, AVISO_AGREGADO)
    if not escuela:
        datos["mensaje"] = "Tu cuenta no tiene escuela asignada."
        return datos
    where, params = where_ambito(user)

    filas = db_adapter.fetch_all(
        f"""
        SELECT grado_secundaria AS grado,
               COUNT(*) AS n,
               AVG(asistencia_pct_calculada) AS asistencia,
               AVG(nota_trimestre_1_0_20) AS t1,
               AVG(nota_trimestre_2_0_20) AS t2,
               AVG(faltas_trimestre_1) AS faltas_t1,
               AVG(faltas_trimestre_2) AS faltas_t2,
               SUM(CASE WHEN internet_hogar = 1 THEN 1 ELSE 0 END) AS con_internet,
               SUM(CASE WHEN promedio_notas_calculado >= {NOTA_APROBATORIA} THEN 1 ELSE 0 END) AS aprobados,
               SUM(CASE WHEN {SUGERIR_REVISION_SQL} THEN 1 ELSE 0 END) AS revision,
               SUM(CASE WHEN beneficiario_juntos = 1 THEN 1 ELSE 0 END) AS juntos,
               SUM(CASE WHEN horas_trabajo_semanal > 0 THEN 1 ELSE 0 END) AS trabaja
        FROM alumnos_hack4edu
        WHERE {where}
        GROUP BY grado_secundaria
        ORDER BY grado_secundaria ASC;
        """,
        params,
    )
    total = sum(_ent(f.get("n")) for f in filas)
    visibles, ocultos = [], []
    for f in filas:
        n = _ent(f.get("n"))
        etiqueta = f"{_ent(f.get('grado'))}.º"
        if n < K_MIN:
            ocultos.append({"grado": _ent(f.get("grado")), "label": etiqueta})
            continue
        visibles.append({
            "grado": _ent(f.get("grado")),
            "label": etiqueta,
            "n": n,
            "asistencia_pct": _num(f.get("asistencia")),
            "nota_t1": _num(f.get("t1")),
            "nota_t2": _num(f.get("t2")),
            "faltas_t1": _num(f.get("faltas_t1")),
            "faltas_t2": _num(f.get("faltas_t2")),
            "internet_pct": _pct(f.get("con_internet"), n),
            "aprobados_pct": _pct(f.get("aprobados"), n),
            "revision": _ent(f.get("revision")),
            "juntos": _ent(f.get("juntos")),
            "trabaja": _ent(f.get("trabaja")),
        })

    if total < K_MIN:
        datos["kpis"] = [_kpi("alumnos", "Estudiantes en tu escuela", total if total == 0 else f"< {K_MIN}")]
        datos["mensaje"] = (
            "Todavía no hay estudiantes cargados para tu escuela." if total == 0
            else f"Hay menos de {K_MIN} estudiantes: los datos se ocultan para proteger su privacidad."
        )
        return datos

    k = db_adapter.fetch_one(
        f"""
        SELECT AVG(asistencia_pct_calculada) AS asistencia,
               AVG(promedio_notas_calculado) AS promedio,
               SUM(CASE WHEN internet_hogar = 1 THEN 1 ELSE 0 END) AS con_internet,
               SUM(CASE WHEN {SUGERIR_REVISION_SQL} THEN 1 ELSE 0 END) AS revision,
               SUM(CASE WHEN beneficiario_juntos = 1 THEN 1 ELSE 0 END) AS juntos
        FROM alumnos_hack4edu WHERE {where};
        """,
        params,
    ) or {}
    datos["hay_datos"] = True
    datos["kpis"] = [
        _kpi("alumnos", "Estudiantes en tu escuela", total, "", f"{len(filas)} grados"),
        _kpi("asistencia", "Asistencia media", _num(k.get("asistencia")), "%"),
        _kpi("promedio", "Nota media", _num(k.get("promedio")), "/20"),
        _kpi("internet", "Con internet en casa", _pct(k.get("con_internet"), total), "%"),
        _kpi("revision", "Sugerencias de revisión", _ent(k.get("revision")), "", "Suma de los grupos"),
        _kpi("juntos", "Familias en el programa Juntos", _ent(k.get("juntos"))),
    ]
    datos["charts"] = {
        "asistencia_por_grado": [{"label": g["label"], "value": g["asistencia_pct"]} for g in visibles],
        "notas_por_grado": {
            "categorias": [g["label"] for g in visibles],
            "series": [
                {"name": "1.er trimestre", "values": [g["nota_t1"] for g in visibles]},
                {"name": "2.º trimestre", "values": [g["nota_t2"] for g in visibles]},
            ],
        },
        "faltas_por_grado": {
            "categorias": [g["label"] for g in visibles],
            "series": [
                {"name": "1.er trimestre", "values": [g["faltas_t1"] for g in visibles]},
                {"name": "2.º trimestre", "values": [g["faltas_t2"] for g in visibles]},
            ],
        },
        "revision_por_grado": [{"label": g["label"], "value": g["revision"]} for g in visibles],
        "internet_por_grado": [{"label": g["label"], "value": g["internet_pct"]} for g in visibles],
    }
    datos["tablas"] = {"grados": visibles, "grados_ocultos": ocultos}
    return datos


# ---------------------------------------------------------------------------
# Delegado: su UGEL, agregada por escuela y por zona (k >= K_MIN)
# ---------------------------------------------------------------------------

def panel_delegado(user: Dict[str, Any]) -> Dict[str, Any]:
    ugel = user.get("ugel")
    datos = _base("delegado", {"ugel": ugel}, AVISO_AGREGADO)
    if not ugel:
        datos["mensaje"] = "Tu cuenta no tiene UGEL asignada."
        return datos
    where, params = where_ambito(user)

    agregados = f"""
               COUNT(*) AS n,
               AVG(asistencia_pct_calculada) AS asistencia,
               AVG(promedio_notas_calculado) AS promedio,
               AVG(distancia_hogar_escuela_km) AS distancia,
               SUM(CASE WHEN internet_hogar = 1 THEN 1 ELSE 0 END) AS con_internet,
               SUM(CASE WHEN {SUGERIR_REVISION_SQL} THEN 1 ELSE 0 END) AS revision,
               SUM(CASE WHEN beneficiario_juntos = 1 THEN 1 ELSE 0 END) AS juntos
    """
    por_escuela = db_adapter.fetch_all(
        f"""
        SELECT escuela_id, MIN(distrito) AS distrito, MIN(zona_escuela) AS zona, {agregados}
        FROM alumnos_hack4edu WHERE {where}
        GROUP BY escuela_id ORDER BY escuela_id ASC;
        """,
        params,
    )
    por_zona = db_adapter.fetch_all(
        f"""
        SELECT zona_escuela AS zona, {agregados}
        FROM alumnos_hack4edu WHERE {where}
        GROUP BY zona_escuela ORDER BY zona_escuela ASC;
        """,
        params,
    )
    total = sum(_ent(f.get("n")) for f in por_escuela)

    def _fila(f: Dict[str, Any]) -> Dict[str, Any]:
        n = _ent(f.get("n"))
        return {
            "n": n,
            "asistencia_pct": _num(f.get("asistencia")),
            "promedio": _num(f.get("promedio")),
            "distancia_km": _num(f.get("distancia"), 2),
            "internet_pct": _pct(f.get("con_internet"), n),
            "revision": _ent(f.get("revision")),
            "juntos": _ent(f.get("juntos")),
        }

    escuelas, ocultas = [], []
    for f in por_escuela:
        if _ent(f.get("n")) < K_MIN:
            ocultas.append({"escuela_id": f["escuela_id"]})
            continue
        fila = {"escuela_id": f["escuela_id"], "distrito": f.get("distrito"), "zona": f.get("zona"), **_fila(f)}
        motivos = []
        if fila["internet_pct"] is not None and fila["internet_pct"] < UMBRAL_CONECTIVIDAD_PCT:
            motivos.append(f"Menos del {UMBRAL_CONECTIVIDAD_PCT:g} % con internet en casa")
        if fila["distancia_km"] is not None and fila["distancia_km"] > UMBRAL_DISTANCIA_KM:
            motivos.append(f"Distancia media mayor de {UMBRAL_DISTANCIA_KM:g} km")
        fila["brechas"] = motivos
        escuelas.append(fila)
    zonas = [{"zona": f.get("zona"), **_fila(f)} for f in por_zona if _ent(f.get("n")) >= K_MIN]

    if total < K_MIN:
        datos["kpis"] = [_kpi("alumnos", "Estudiantes en tu UGEL", total if total == 0 else f"< {K_MIN}")]
        datos["mensaje"] = (
            "Todavía no hay estudiantes cargados para tu UGEL." if total == 0
            else f"Hay menos de {K_MIN} estudiantes: los datos se ocultan para proteger su privacidad."
        )
        return datos

    k = db_adapter.fetch_one(
        f"SELECT {agregados}, SUM(CASE WHEN UPPER(zona_escuela) = 'RURAL' THEN 1 ELSE 0 END) AS rurales "
        f"FROM alumnos_hack4edu WHERE {where};",
        params,
    ) or {}
    datos["hay_datos"] = True
    datos["kpis"] = [
        _kpi("escuelas", "Escuelas con datos", len(por_escuela)),
        _kpi("alumnos", "Estudiantes", total, "", f"{_pct(k.get('rurales'), total) or 0:g} % en zona rural"),
        _kpi("asistencia", "Asistencia media", _num(k.get("asistencia")), "%"),
        _kpi("promedio", "Nota media", _num(k.get("promedio")), "/20"),
        _kpi("internet", "Con internet en casa", _pct(k.get("con_internet"), total), "%"),
        _kpi("brechas", "Escuelas con brecha", sum(1 for e in escuelas if e["brechas"]), "",
             f"Internet < {UMBRAL_CONECTIVIDAD_PCT:g} % o distancia > {UMBRAL_DISTANCIA_KM:g} km"),
    ]
    datos["charts"] = {
        "asistencia_por_escuela": [{"label": e["escuela_id"], "value": e["asistencia_pct"]} for e in escuelas],
        "internet_por_escuela": [{"label": e["escuela_id"], "value": e["internet_pct"]} for e in escuelas],
        "revision_por_escuela": [{"label": e["escuela_id"], "value": e["revision"]} for e in escuelas],
        "comparativa_zonas": {
            "categorias": ["Asistencia (%)", "Internet en casa (%)"],
            "series": [
                {"name": z["zona"], "values": [z["asistencia_pct"], z["internet_pct"]]} for z in zonas
            ],
        },
    }
    datos["tablas"] = {
        "escuelas": escuelas,
        "escuelas_ocultas": ocultas,
        "zonas": zonas,
        "brechas": [e for e in escuelas if e["brechas"]],
    }
    return datos


PANELES = {"docente": panel_docente, "director": panel_director, "delegado": panel_delegado}


@router.get("", summary="Panel con gráficos del rol de la sesión")
def mi_panel(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return PANELES[user["rol"]](user)


@router.get("/{rol}", summary="Panel de un rol concreto (403 si no es el tuyo)")
def panel_por_rol(rol: str, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if rol not in ROLES:
        raise HTTPException(status_code=404, detail="Ese panel no existe.")
    if rol != user["rol"]:
        raise HTTPException(status_code=403, detail="Tu rol no tiene acceso a este panel.")
    return PANELES[rol](user)
