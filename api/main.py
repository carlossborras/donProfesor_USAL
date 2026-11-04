"""
DONPROFESOR (#Hack4Edu 2026, Reto 13) · Backend API y puente MCP.
Conecta 100% a la Base de Datos real (PostgreSQL o SQLite local vía db_adapter)
SIN simulaciones ni números hardcodeados: todos los KPIs, tablas y avisos se calculan
dinámicamente con SQL sobre las 37 variables oficiales (`alumnos_hack4edu`).
"""

from __future__ import annotations
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from db.seed_db import init_and_seed_database
from db.adapter import db_adapter
from db.students import where_ambito
from model import config as model_config
from mcp_server.db_mcp_server import list_tables
from mcp_server.chat_agent import answer_pedagogical_chat_with_mcp, check_remote_llm_health
from api.security import get_current_user
from api.auth import router as auth_router
from api.dashboards import router as dashboard_router
from api.datos import router as datos_router
from api.predictions import router as predictions_router

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "web" / "frontend"

# Cargar automáticamente variables de entorno desde .env si existe
_env_path = ROOT_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# El secreto JWT, el registro y el login viven en api/security.py y api/auth.py


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    init_and_seed_database(force_reset=False)
    yield


app = FastAPI(
    title="DONPROFESOR — Plataforma de Analítica Educativa Acompañada (#Hack4Edu)",
    description=(
        "API con control de acceso por rol, predicciones del modelo LightGBM + Random Forest al dar de alta "
        "estudiantes, paneles por rol y asistente conectado a la base de datos mediante MCP."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

if (FRONTEND_DIR / "dist" / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "dist" / "assets")), name="react_assets")
if (FRONTEND_DIR / "src").exists():
    app.mount("/src", StaticFiles(directory=str(FRONTEND_DIR / "src")), name="react_src")

# Registro, inicio de sesión y paneles con gráficos por rol
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(datos_router)
app.include_router(predictions_router)


class ActionCreateRequest(BaseModel):
    alumno_id: str = Field(min_length=1, max_length=32)
    decision_tomada: str = Field(min_length=1, max_length=200)
    comentario_pedagogico: Optional[str] = Field(default=None, max_length=2000)


class GrantSimulationRequest(BaseModel):
    presupuesto_total: float = Field(gt=0, le=1e12)
    pct_transporte: float = Field(ge=0, le=100)
    pct_beca: float = Field(ge=0, le=100)
    pct_refuerzo: float = Field(ge=0, le=100)


class ChatMCPRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


def _contar_ambito(user: Dict[str, Any]) -> Dict[str, Any]:
    where, params = where_ambito(user)
    fila = db_adapter.fetch_one(
        f"SELECT COUNT(*) AS total, SUM(CASE WHEN necesidad_intervencion IS NOT NULL THEN 1 ELSE 0 END) AS con_pred "
        f"FROM alumnos_hack4edu WHERE {where};",
        params,
    ) or {}
    total, con_pred = int(fila.get("total") or 0), int(fila.get("con_pred") or 0)
    return {
        "total_alumnos_cargados": total,
        "total_predicciones_cargadas": con_pred,
        "estado_datos": "datos_listos" if total > 0 else "vacia_esperando_carga",
        "mensaje": f"{total} estudiantes en tu ámbito ({con_pred} con predicción)." if total else "Todavía no hay estudiantes en tu ámbito.",
    }


@app.get("/api/db-status")
def get_database_status(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Estado de la base de datos y número de estudiantes del ámbito de la sesión."""
    return {**db_adapter.get_status_metadata(), **_contar_ambito(user)}


def _factores_aviso(fila: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        datos = json.loads(fila.get("factores_json") or "[]")
    except ValueError:
        datos = []
    return [
        {"texto": f.get("texto"), "peso": f.get("peso_relativo"), "sugerencia": f.get("sugerencia")}
        for f in datos if isinstance(f, dict) and f.get("texto")
    ]


def _nombre(user: Dict[str, Any]) -> str:
    return user.get("nombre_completo") or user.get("sub")


@app.get("/api/panel")
def get_role_dashboard_panel(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """«Para revisar»: estudiantes del ámbito con necesidad de intervención Alta o Media según el modelo.

    Cada aviso lleva los factores del propio estudiante que más empujan la predicción y su peso relativo
    (reparto de la explicación, no una probabilidad). Sin porcentajes de riesgo y orden por código.
    """
    rol = user["rol"]
    where, params = where_ambito(user)
    avisos = db_adapter.fetch_all(
        f"""
        SELECT alumno_id, escuela_id, grado_secundaria, necesidad_intervencion, prediccion_nota_t3,
               prediccion_faltas_t3, factores_json, recomendacion_pedagogica, fecha_prediccion
        FROM alumnos_hack4edu
        WHERE {where} AND necesidad_intervencion IN ('Alta', 'Media')
        ORDER BY alumno_id ASC;
        """,
        params,
    )
    revisados = {
        r["alumno_id"]
        for r in db_adapter.fetch_all(
            "SELECT DISTINCT alumno_id FROM registro_accion_humana WHERE usuario_nombre = ? AND rol_usuario = ?;",
            (_nombre(user), rol),
        )
    }
    avisos_formateados = []
    for a in avisos:
        detalle = []
        if a.get("prediccion_nota_t3") is not None:
            detalle.append(f"Nota prevista en el 3.er trimestre: {float(a['prediccion_nota_t3']):g}/20")
        if a.get("prediccion_faltas_t3") is not None:
            detalle.append(f"faltas previstas en el 3.er trimestre: {int(a['prediccion_faltas_t3'])}")
        avisos_formateados.append({
            "prediccion_id": a["alumno_id"],
            "codigo_seguimiento": a["alumno_id"],
            "titulo_humano": f"Estudiante {a['alumno_id']} · sugerencia de revisión",
            "categoria_contexto": f"Necesidad de intervención {str(a['necesidad_intervencion']).lower()}",
            "escuela_id": a["escuela_id"],
            "grado_id": f"{a['grado_secundaria']}.º",
            "estado_revision": "Revisado" if a["alumno_id"] in revisados else "Pendiente de revisión",
            "descripcion_situacion": " · ".join(detalle) or None,
            "factores": _factores_aviso(a),
            "recomendacion_pedagogica": a.get("recomendacion_pedagogica"),
            "accion_sugerida_boton": "Registrar acuerdo",
            "fecha_prediccion": a.get("fecha_prediccion"),
        })

    acciones = db_adapter.fetch_all(
        "SELECT accion_id, alumno_id, decision_tomada, comentario_pedagogico, fecha_registro "
        "FROM registro_accion_humana WHERE usuario_nombre = ? AND rol_usuario = ? ORDER BY accion_id DESC LIMIT 10;",
        (_nombre(user), rol),
    )
    return {
        "user": {k: user.get(k) for k in ("username", "nombre_completo", "rol", "escuela_id", "grado_secundaria", "ugel")},
        "db_status": {**db_adapter.get_status_metadata(), **_contar_ambito(user)},
        "sql_security": {
            "db_role": f"role_{rol}",
            "granted_views": {"docente": ["vista_docente"], "director": ["vista_director"], "delegado": ["vista_delegado"]}[rol],
            "ethical_banner": "La decisión es tuya; el modelo puede equivocarse.",
        },
        "avisos_predictivos": avisos_formateados,
        "acciones_humanas": acciones,
    }


@app.post("/api/acciones")
def register_human_action(req: ActionCreateRequest, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Registra la decisión de una persona sobre un estudiante de SU ámbito."""
    where, params = where_ambito(user)
    if not db_adapter.fetch_one(f"SELECT alumno_id FROM alumnos_hack4edu WHERE alumno_id = ? AND {where};", (req.alumno_id,) + params):
        raise HTTPException(status_code=404, detail="Ese estudiante no existe en tu ámbito.")
    ambito = {"docente": f"{user.get('escuela_id')}/{user.get('grado_secundaria')}",
              "director": user.get("escuela_id"), "delegado": user.get("ugel")}[user["rol"]]
    db_adapter.execute_write(
        "INSERT INTO registro_accion_humana (alumno_id, rol_usuario, usuario_nombre, ambito_id, decision_tomada, "
        "comentario_pedagogico) VALUES (?, ?, ?, ?, ?, ?);",
        (req.alumno_id, user["rol"], _nombre(user), ambito,
         req.decision_tomada.strip(), (req.comentario_pedagogico or "").strip() or None),
    )
    return {"status": "ok", "message": "Decisión guardada.", "alumno_id": req.alumno_id}


@app.post("/api/simular-subvencion")
def simulate_territorial_grant(req: GrantSimulationRequest, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Reparto de un presupuesto en tu ámbito según los datos y las predicciones (sin efectos inventados).

    Cuenta, con datos reales, cuántos estudiantes encajan en cada línea y cuánto dinero le tocaría a cada uno:
      - transporte: viven a más de DONPROFESOR_DISTANCIA_TRANSPORTE_KM o tardan 30 min o más
      - beca: familias en Juntos con probabilidad alta de perder la beca
      - refuerzo: necesidad de intervención alta o probabilidad alta de repetir
    """
    total_pct = req.pct_transporte + req.pct_beca + req.pct_refuerzo
    if total_pct <= 0:
        raise HTTPException(status_code=422, detail="Reparte al menos un porcentaje del presupuesto.")
    distancia = float(os.environ.get("DONPROFESOR_DISTANCIA_TRANSPORTE_KM", "3"))
    alto = model_config.umbral_alto() * 100
    where, params = where_ambito(user)
    fila = db_adapter.fetch_one(
        f"""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN distancia_hogar_escuela_km > ? OR tiempo_desplazamiento IN ('30-60 min', 'Mas de 60 min')
                        THEN 1 ELSE 0 END) AS transporte,
               SUM(CASE WHEN beneficiario_juntos = 1 AND prob_perdida_beca_pct >= ? THEN 1 ELSE 0 END) AS beca,
               SUM(CASE WHEN necesidad_intervencion = 'Alta' OR prob_repeticion_pct >= ? THEN 1 ELSE 0 END) AS refuerzo,
               SUM(CASE WHEN necesidad_intervencion IS NULL THEN 1 ELSE 0 END) AS sin_prediccion
        FROM alumnos_hack4edu WHERE {where};
        """,
        (distancia, alto, alto) + params,
    ) or {}
    moneda = os.environ.get("DONPROFESOR_MONEDA", "PEN")
    total = int(fila.get("total") or 0)
    if total < model_config.k_minimo():
        return {"moneda": moneda, "lineas": [], "total": None,
                "lectura_humanizada": f"Hay menos de {model_config.k_minimo()} estudiantes en tu ámbito: no se muestra el reparto."}
    lineas = []
    for clave, etiqueta, pct in (
        ("transporte", f"Transporte (más de {distancia:g} km o 30 min o más)", req.pct_transporte),
        ("beca", "Protección de la beca Juntos (probabilidad alta de perderla)", req.pct_beca),
        ("refuerzo", "Refuerzo y tutoría (necesidad alta o probabilidad alta de repetir)", req.pct_refuerzo),
    ):
        importe = req.presupuesto_total * pct / total_pct
        n = int(fila.get(clave) or 0)
        lineas.append({
            "linea": clave, "etiqueta": etiqueta, "pct": round(100 * pct / total_pct, 1),
            "importe": round(importe, 2), "estudiantes": n, "por_estudiante": round(importe / n, 2) if n else None,
        })
    texto = "; ".join(
        f"{l['etiqueta']}: {l['importe']:,.0f} {moneda} para {l['estudiantes']} estudiantes"
        + (f" ({l['por_estudiante']:,.0f} {moneda} cada uno)" if l["por_estudiante"] else "")
        for l in lineas
    )
    pendientes = int(fila.get("sin_prediccion") or 0)
    aviso = f" {pendientes} estudiantes aún no tienen predicción y no cuentan en beca ni refuerzo." if pendientes else ""
    return {"moneda": moneda, "total": total, "lineas": lineas, "sin_prediccion": pendientes,
            "lectura_humanizada": f"Con los datos de tu ámbito ({total} estudiantes): {texto}.{aviso}"}


@app.get("/api/config/llm")
def get_llm_status_endpoint(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Devuelve el estado de conexión con el servidor Qwen/vLLM remoto."""
    return check_remote_llm_health()


# =============================================================================
# ENDPOINTS DEL SERVIDOR MCP Y CHAT CONECTADO A LA BASE DE DATOS
# =============================================================================

@app.get("/api/mcp/tools")
def get_mcp_tools_metadata(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    rol = user["rol"]
    vistas = list_tables(rol)
    return {
        "mcp_server_name": "donprofesor-db-mcp",
        "protocol": "Model Context Protocol (MCP)",
        "active_db_role": f"role_{rol}",
        "tools": [
            {
                "name": "list_tables",
                "description": "Lista las vistas SQL autorizadas para el rol activo.",
            },
            {
                "name": "describe_table",
                "description": "Inspecciona las columnas de una vista autorizada.",
            },
            {
                "name": "read_query",
                "description": "Ejecuta una consulta SQL SELECT de solo lectura sobre las vistas autorizadas.",
            },
        ],
        "accessible_views": vistas,
    }


@app.post("/api/chat-mcp")
def chat_with_mcp_endpoint(
    req: ChatMCPRequest, user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    ambito = {k: user.get(k) for k in ("escuela_id", "grado_secundaria", "ugel")}
    return answer_pedagogical_chat_with_mcp(user["rol"], ambito, req.question)


@app.get("/", response_class=HTMLResponse)
def serve_donprofesor_react_app() -> HTMLResponse:
    dist_index = FRONTEND_DIR / "dist" / "index.html"
    if dist_index.exists():
        return HTMLResponse(content=dist_index.read_text(encoding="utf-8"))
    react_index = FRONTEND_DIR / "index.html"
    return HTMLResponse(content=react_index.read_text(encoding="utf-8"))
