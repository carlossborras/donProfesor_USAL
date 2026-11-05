"""
DONPROFESOR (#Hack4Edu 2026, Reto 13) · Pestaña «Predicciones» y estado del modelo.

  GET  /api/modelo/estado              -> ¿está cargado el modelo? versión, variables, umbrales
  GET  /api/modelo/campos              -> campos y categorías que aprendió el modelo (formularios)
  GET  /api/predicciones               -> vista de predicciones del rol de la sesión
  POST /api/predicciones/recalcular    -> vuelve a predecir a los estudiantes del ámbito

La importancia de cada indicador para cada rol sigue la tabla acordada por el equipo
(PRIORIDADES). Todo se muestra; el orden y el protagonismo dependen del interés (alta > media > baja).

Ética:
  - Docente: a nivel individual solo NIVELES (alto / medio / bajo), nunca porcentajes ni rankings
    (alumnos ordenados por código). A nivel de clase, porcentajes agregados.
  - Director y delegado: solo agregados; grupos con menos de k estudiantes se ocultan.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from api.security import get_current_user, require_role
from db.adapter import db_adapter
from db.students import where_ambito, recalcular
from model import config, predictor

router = APIRouter(tags=["predicciones"])

INTERES_ORDEN = {"alta": 0, "media": 1, "baja": 2}

# Tabla del equipo: interés de cada rol por cada indicador del modelo
PRIORIDADES: Dict[str, Dict[str, str]] = {
    "docente": {
        "necesidad": "alta", "desanimo": "alta", "notas": "alta", "faltas": "alta",
        "abandono": "media", "repeticion": "media", "beca": "baja",
    },
    "director": {
        "abandono": "alta", "necesidad": "alta", "beca": "alta", "repeticion": "alta", "faltas": "alta",
        "desanimo": "media", "notas": "media",
    },
    "delegado": {
        "abandono": "alta", "beca": "alta", "repeticion": "alta",
        "necesidad": "baja", "desanimo": "baja", "notas": "baja", "faltas": "baja",
    },
}

TITULOS = {
    "abandono": "Abandono escolar",
    "beca": "Pérdida de la beca (Juntos)",
    "repeticion": "Repetición de curso",
    "necesidad": "Necesidad de intervención",
    "desanimo": "Desánimo",
    "notas": "Notas previstas",
    "faltas": "Faltas previstas",
}

SUJETO = {"docente": "tu clase", "director": "tu escuela", "delegado": "tu UGEL"}

COLUMNAS = (
    "alumno_id, escuela_id, ugel, distrito, zona_escuela, grado_secundaria, beneficiario_juntos, "
    "nota_trimestre_1_0_20, nota_trimestre_2_0_20, faltas_trimestre_1, faltas_trimestre_2, "
    "prob_abandono_pct, prob_perdida_beca_pct, prob_repeticion_pct, necesidad_intervencion, "
    "prediccion_nota_t1, prediccion_nota_t2, prediccion_nota_t3, "
    "prediccion_faltas_t1, prediccion_faltas_t2, prediccion_faltas_t3, indice_desanimo, "
    "factores_json, recomendacion_pedagogica, modelo_version, fecha_prediccion"
)


# ---------------------------------------------------------------------------
# Utilidades de cálculo
# ---------------------------------------------------------------------------

def _f(v: Any) -> Optional[float]:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _media(valores: List[Optional[float]], dec: int = 1) -> Optional[float]:
    v = [x for x in valores if x is not None]
    return round(sum(v) / len(v), dec) if v else None


def _pct(parte: int, total: int) -> Optional[float]:
    return round(100.0 * parte / total, 1) if total else None


def _niveles(filas: List[Dict[str, Any]], columna: str) -> Dict[str, int]:
    cuenta = {"alto": 0, "medio": 0, "bajo": 0}
    for f in filas:
        n = predictor.nivel_probabilidad(_f(f.get(columna)))
        if n:
            cuenta[n] += 1
    return cuenta


def _base_beca(filas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [f for f in filas if int(f.get("beneficiario_juntos") or 0) == 1 and f.get("prob_perdida_beca_pct") is not None]


def _con_pred(filas: List[Dict[str, Any]], columna: str) -> List[Dict[str, Any]]:
    return [f for f in filas if f.get(columna) is not None]


def _fmt(v: Optional[float]) -> str:
    return "—" if v is None else (f"{v:g}" if float(v).is_integer() else f"{v:.1f}".replace(".", ","))


# ---------------------------------------------------------------------------
# Indicadores (resumen global de un conjunto de estudiantes)
# ---------------------------------------------------------------------------

def _resumen_probabilidad(filas, columna, verbo, sujeto) -> Dict[str, Any]:
    base = _con_pred(filas, columna)
    niveles = _niveles(base, columna)
    total = len(base)
    esperados = round(sum(_f(f[columna]) or 0 for f in base) / 100.0, 1)
    frases = []
    if total:
        frases.append(f"El {_fmt(_pct(niveles['alto'], total))} % de {sujeto} tiene una probabilidad alta de {verbo}.")
        if niveles["medio"]:
            frases.append(f"Otro {_fmt(_pct(niveles['medio'], total))} % tiene una probabilidad media.")
    return {
        "base": total,
        "niveles": niveles,
        "pct_alto": _pct(niveles["alto"], total),
        "pct_medio": _pct(niveles["medio"], total),
        "estudiantes_esperados": esperados if total else None,
        "frases": frases,
    }


def indicador(clave: str, filas: List[Dict[str, Any]], sujeto: str) -> Dict[str, Any]:
    if clave == "abandono":
        return _resumen_probabilidad(filas, "prob_abandono_pct", "abandonar los estudios", sujeto)
    if clave == "repeticion":
        return _resumen_probabilidad(filas, "prob_repeticion_pct", "repetir curso", sujeto)
    if clave == "beca":
        base = _base_beca(filas)
        r = _resumen_probabilidad(base, "prob_perdida_beca_pct", "perder la beca", "esas familias")
        r["familias_juntos"] = sum(1 for f in filas if int(f.get("beneficiario_juntos") or 0) == 1)
        r["frases"] = (
            [f"{r['familias_juntos']} estudiantes de {sujeto} tienen familia en el programa Juntos."] + r["frases"]
            if r["familias_juntos"] else [f"Ninguna familia de {sujeto} está en el programa Juntos."]
        )
        return r
    if clave == "necesidad":
        base = _con_pred(filas, "necesidad_intervencion")
        cuenta = {k: sum(1 for f in base if f["necesidad_intervencion"] == k) for k in ("Alta", "Media", "Baja")}
        total = len(base)
        frases = []
        if total:
            frases.append(f"El {_fmt(_pct(cuenta['Alta'], total))} % de {sujeto} tiene una necesidad alta de intervención "
                          f"y el {_fmt(_pct(cuenta['Media'], total))} % media.")
        return {"base": total, "clases": cuenta, "pct_alta": _pct(cuenta["Alta"], total),
                "pct_media": _pct(cuenta["Media"], total), "frases": frases}
    if clave == "desanimo":
        base = _con_pred(filas, "indice_desanimo")
        niveles = {"alto": 0, "medio": 0, "bajo": 0}
        for f in base:
            niveles[predictor.nivel_desanimo(_f(f["indice_desanimo"]))] += 1
        total = len(base)
        media = _media([_f(f["indice_desanimo"]) for f in base])
        frases = [f"Desánimo medio previsto: {_fmt(media)} sobre 10. "
                  f"El {_fmt(_pct(niveles['alto'], total))} % de {sujeto} tiene un desánimo alto."] if total else []
        return {"base": total, "media": media, "niveles": niveles, "pct_alto": _pct(niveles["alto"], total), "frases": frases}
    if clave == "notas":
        base = _con_pred(filas, "prediccion_nota_t3")
        total = len(base)
        suspenden = sum(1 for f in base if _f(f["prediccion_nota_t3"]) < config.NOTA_APROBATORIA)
        reales = {"t1": _media([_f(f.get("nota_trimestre_1_0_20")) for f in filas]),
                  "t2": _media([_f(f.get("nota_trimestre_2_0_20")) for f in filas])}
        previstas = {t: _media([_f(f.get(f"prediccion_nota_{t}")) for f in base]) for t in ("t1", "t2", "t3")}
        frases = [f"El {_fmt(_pct(suspenden, total))} % de {sujeto} tiene una nota prevista del 3.er trimestre "
                  f"por debajo de {config.NOTA_APROBATORIA:g} (suspenso)."] if total else []
        return {"base": total, "reales": reales, "previstas": previstas,
                "pct_suspenso_t3": _pct(suspenden, total), "frases": frases}
    if clave == "faltas":
        base = _con_pred(filas, "prediccion_faltas_t3")
        reales = {"t1": _media([_f(f.get("faltas_trimestre_1")) for f in filas]),
                  "t2": _media([_f(f.get("faltas_trimestre_2")) for f in filas])}
        previstas = {t: _media([_f(f.get(f"prediccion_faltas_{t}")) for f in base]) for t in ("t1", "t2", "t3")}
        frases = [f"Faltas previstas en el 3.er trimestre: {_fmt(previstas['t3'])} días de media por estudiante."] if base else []
        return {"base": len(base), "reales": reales, "previstas": previstas, "frases": frases}
    raise ValueError(clave)


# ---------------------------------------------------------------------------
# Desgloses (director: por grado; delegado: por escuela y zona) con k-anonimato
# ---------------------------------------------------------------------------

def _desglose(filas, clave_grupo: Callable[[Dict[str, Any]], Any], etiqueta: Callable[[Any], str]) -> Dict[str, Any]:
    grupos: Dict[Any, List[Dict[str, Any]]] = {}
    for f in filas:
        grupos.setdefault(clave_grupo(f), []).append(f)
    k = config.k_minimo()
    visibles, ocultos = [], []
    for g in sorted(grupos, key=lambda x: (x is None, str(x))):
        miembros = grupos[g]
        if len(miembros) < k:
            ocultos.append(etiqueta(g))
            continue
        con = _con_pred(miembros, "necesidad_intervencion")
        beca = _base_beca(miembros)
        visibles.append({
            "grupo": g,
            "label": etiqueta(g),
            "n": len(miembros),
            "con_prediccion": len(con),
            "pct_abandono_alto": _pct(_niveles(con, "prob_abandono_pct")["alto"], len(_con_pred(con, "prob_abandono_pct"))),
            "pct_repeticion_alto": _pct(_niveles(con, "prob_repeticion_pct")["alto"], len(_con_pred(con, "prob_repeticion_pct"))),
            "familias_juntos": sum(1 for f in miembros if int(f.get("beneficiario_juntos") or 0) == 1),
            "pct_beca_alto": _pct(_niveles(beca, "prob_perdida_beca_pct")["alto"], len(beca)),
            "abandonos_esperados": round(sum(_f(f.get("prob_abandono_pct")) or 0 for f in con) / 100.0, 1) if con else None,
            "necesidad_alta": sum(1 for f in con if f["necesidad_intervencion"] == "Alta"),
            "necesidad_media": sum(1 for f in con if f["necesidad_intervencion"] == "Media"),
            "desanimo_medio": _media([_f(f.get("indice_desanimo")) for f in con]),
            "nota_t3_prevista": _media([_f(f.get("prediccion_nota_t3")) for f in con]),
            "pct_suspenso_t3": _pct(sum(1 for f in con if (_f(f.get("prediccion_nota_t3")) or 99) < config.NOTA_APROBATORIA), len(con)),
            "faltas_t3_previstas": _media([_f(f.get("prediccion_faltas_t3")) for f in con]),
        })
    return {"grupos": visibles, "ocultos": ocultos}


# ---------------------------------------------------------------------------
# Tabla individual del docente (niveles, sin porcentajes, orden por código)
# ---------------------------------------------------------------------------

def _factores(valor: Any) -> List[Dict[str, Any]]:
    if not valor:
        return []
    try:
        datos = json.loads(valor) if isinstance(valor, str) else valor
    except ValueError:
        return []
    return [{"texto": f.get("texto"), "sugerencia": f.get("sugerencia")} for f in datos if isinstance(f, dict)]


def _alumno_docente(f: Dict[str, Any]) -> Dict[str, Any]:
    juntos = int(f.get("beneficiario_juntos") or 0) == 1
    pendiente = f.get("necesidad_intervencion") is None
    return {
        "alumno_id": f["alumno_id"],
        "prediccion_pendiente": pendiente,
        "sugerir_revision": f.get("necesidad_intervencion") in ("Alta", "Media"),
        "necesidad": (f.get("necesidad_intervencion") or "").lower() or None,
        "abandono": predictor.nivel_probabilidad(_f(f.get("prob_abandono_pct"))),
        "repeticion": predictor.nivel_probabilidad(_f(f.get("prob_repeticion_pct"))),
        "beca": predictor.nivel_probabilidad(_f(f.get("prob_perdida_beca_pct"))) if juntos else None,
        "desanimo": predictor.nivel_desanimo(_f(f.get("indice_desanimo"))),
        "nota_t1": _f(f.get("nota_trimestre_1_0_20")),
        "nota_t2": _f(f.get("nota_trimestre_2_0_20")),
        "nota_t3_prevista": _f(f.get("prediccion_nota_t3")),
        "faltas_t3_previstas": _f(f.get("prediccion_faltas_t3")),
        # Los factores solo se muestran cuando el modelo sugiere revisar (necesidad Alta o Media):
        # en estudiantes sin riesgo la explicación recoge variaciones mínimas que confunden.
        "factores": _factores(f.get("factores_json")) if f.get("necesidad_intervencion") in ("Alta", "Media") else [],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/modelo/estado", summary="Estado del modelo predictivo")
def estado_modelo(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return predictor.model_status()


@router.get("/api/modelo/campos", summary="Campos y categorías de entrada del modelo")
def campos_modelo(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        return predictor.input_fields()
    except predictor.ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


@router.post("/api/predicciones/recalcular", summary="Recalcular las predicciones del ámbito")
def recalcular_predicciones(solo_pendientes: bool = False, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    resultado = recalcular(user, solo_pendientes=solo_pendientes)
    if resultado["aviso"]:
        raise HTTPException(status_code=503, detail=resultado["aviso"])
    return {"status": "ok", "message": f"Predicciones recalculadas para {resultado['calculadas']} estudiantes.", **resultado}


@router.get("/api/predicciones", summary="Predicciones del rol de la sesión")
def predicciones(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    rol = user["rol"]
    where, params = where_ambito(user)
    filas = db_adapter.fetch_all(f"SELECT {COLUMNAS} FROM alumnos_hack4edu WHERE {where} ORDER BY alumno_id;", params)
    total = len(filas)
    con_prediccion = sum(1 for f in filas if f.get("necesidad_intervencion") is not None)
    k = config.k_minimo()
    estado = predictor.model_status()
    respuesta: Dict[str, Any] = {
        "rol": rol,
        "scope": {k_: user.get(k_) for k_ in ("escuela_id", "grado_secundaria", "ugel")},
        "modelo": {"disponible": estado["disponible"], "version": estado.get("version"), "error": estado.get("error")},
        "umbrales": {"riesgo_alto_pct": round(config.umbral_alto() * 100), "riesgo_medio_pct": round(config.umbral_medio() * 100),
                     "desanimo_alto": config.desanimo_alto(), "desanimo_medio": config.desanimo_medio()},
        "nota_aprobatoria": config.NOTA_APROBATORIA,
        "k_minimo": k,
        "total": total,
        "con_prediccion": con_prediccion,
        "pendientes": total - con_prediccion,
        "secciones": [],
        "tablas": {},
        "mensaje": None,
    }
    if total == 0:
        respuesta["mensaje"] = "Todavía no hay estudiantes en tu ámbito."
        return respuesta
    if rol != "docente" and total < k:
        respuesta["mensaje"] = f"Hay menos de {k} estudiantes: los datos se ocultan para proteger su privacidad."
        respuesta["total"] = None
        return respuesta
    if con_prediccion == 0:
        respuesta["mensaje"] = "Aún no hay predicciones para tus estudiantes."
        return respuesta

    sujeto = SUJETO[rol]
    prioridades = PRIORIDADES[rol]
    respuesta["secciones"] = [
        {"id": clave, "titulo": TITULOS[clave], "interes": interes, **indicador(clave, filas, sujeto)}
        for clave, interes in sorted(prioridades.items(), key=lambda kv: INTERES_ORDEN[kv[1]])
    ]
    if rol == "docente":
        respuesta["tablas"]["alumnos"] = [_alumno_docente(f) for f in filas]
    elif rol == "director":
        respuesta["tablas"]["grados"] = _desglose(filas, lambda f: f.get("grado_secundaria"), lambda g: f"{g}.º")
    else:
        respuesta["tablas"]["escuelas"] = _desglose(filas, lambda f: f.get("escuela_id"), lambda g: str(g))
        respuesta["tablas"]["zonas"] = _desglose(filas, lambda f: f.get("zona_escuela") or "Sin zona", lambda g: str(g))
    return respuesta
