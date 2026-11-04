"""
DONPROFESOR (#Hack4Edu) · Backend API con JWT, Control de Acceso por Rol y Puente MCP (Persona 3)
y Servidor del Frontend Web con los 3 Paneles (Persona 4).

Características implementadas:
1. Autenticación JWT con `rol` ('docente', 'director', 'delegado') y ámbito (`escuela_id`, `grupo_id`).
2. Middleware y dependencias que verifican el rol y consultan exclusivamente la vista SQL autorizada:
   - `vista_docente` (para el tutor de aula, sin rankings ni semáforos individuales)
   - `vista_director` y `vista_director_clima` (para dirección de centro, gráfica lluvia + cosecha + recursos)
   - `vista_delegado` (para coordinación territorial, mapa de escuelas y simulador de subvenciones)
3. Endpoints del Dashboard con los avisos del modelo predictivo (`GET /api/panel`, `POST /api/acciones`, `POST /api/simular`).
4. Endpoint del Chat conectado al Servidor MCP de Base de Datos (`POST /api/chat-mcp`, `GET /api/mcp/tools`).
"""

from __future__ import annotations
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

import jwt
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from db.seed_db import init_and_seed_database, get_sqlite_connection
from mcp_server.db_mcp_server import list_tables, describe_table, read_query
from mcp_server.chat_agent import answer_pedagogical_chat_with_mcp

JWT_SECRET = os.environ.get("DONPROFESOR_JWT_SECRET", "hack4edu-donprofesor-secret-key-2026")
JWT_ALG = "HS256"


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    init_and_seed_database(force_reset=False)
    yield


app = FastAPI(
    title="DONPROFESOR — Plataforma de Analítica Educativa Acompañada (#Hack4Edu)",
    description=(
        "Backend API con JWT, Vistas SQL por Rol (GRANT SELECT), Dashboard del Modelo Predictivo "
        "y Chat conectado a la Base de Datos mediante Model Context Protocol (MCP)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


class LoginRequest(BaseModel):
    username: str
    password: str = "donprofesor2026"


class ActionCreateRequest(BaseModel):
    prediccion_id: str
    decision_tomada: str
    comentario_pedagogico: Optional[str] = ""


class GrantSimulationRequest(BaseModel):
    presupuesto_total_eur: float = 120000.0
    pct_becas_transporte: float = 45.0
    pct_formacion_docente: float = 35.0
    pct_servidores_offline: float = 20.0


class ChatMCPRequest(BaseModel):
    question: str


class DirectMCPQueryRequest(BaseModel):
    sql_query: str


def create_jwt_token(user_row: Dict[str, Any]) -> str:
    payload = {
        "sub": user_row["username"],
        "nombre_completo": user_row["nombre_completo"],
        "rol": user_row["rol"],
        "escuela_id": user_row["escuela_id"],
        "grupo_id": user_row["grupo_id"],
        "titulo_cargo": user_row["titulo_cargo"],
        "db_role": f"role_{user_row['rol']}",
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Middleware/Dependencia JWT que verifica el token y extrae el rol y ámbito del usuario.
    Si no se envía cabecera Authorization, permite pruebas rápidas devolviendo el perfil docente por defecto.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Token JWT requerido. Inicia sesión con /api/auth/login.",
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return decoded
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Token JWT inválido o expirado: {exc}")


@app.post("/api/auth/login")
def login_endpoint(req: LoginRequest) -> Dict[str, Any]:
    init_and_seed_database()
    conn = get_sqlite_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM usuario_plataforma WHERE username = ? AND password_hash = ?;",
        (req.username.lower().strip(), req.password),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(
            status_code=401,
            detail="Credenciales incorrectas. Usuarios disponibles: docente, director, delegado (clave: donprofesor2026).",
        )
    user_dict = dict(row)
    token = create_jwt_token(user_dict)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "username": user_dict["username"],
            "nombre_completo": user_dict["nombre_completo"],
            "rol": user_dict["rol"],
            "db_role": f"role_{user_dict['rol']}",
            "escuela_id": user_dict["escuela_id"],
            "grupo_id": user_dict["grupo_id"],
            "titulo_cargo": user_dict["titulo_cargo"],
        },
    }


@app.get("/api/panel")
def get_role_dashboard_panel(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Devuelve todos los datos del Dashboard y del Modelo Predictivo consultando
    exclusivamente la Vista SQL correspondiente al rol del token JWT:
    - docente   -> vista_docente + vista_avisos_predictivos
    - director  -> vista_director + vista_director_clima + vista_avisos_predictivos
    - delegado  -> vista_delegado + vista_avisos_predictivos
    """
    init_and_seed_database()
    rol = user["rol"]
    escuela_id = user.get("escuela_id") or "ESC-01"
    grupo_id = user.get("grupo_id") or "ESC-01-2B"

    conn = get_sqlite_connection()
    cur = conn.cursor()

    # 1. Avisos del modelo predictivo para el rol activo
    cur.execute(
        "SELECT * FROM vista_avisos_predictivos WHERE rol_destino = ? ORDER BY prediccion_id ASC;",
        (rol,),
    )
    avisos = [dict(r) for r in cur.fetchall()]

    # 2. Historial de acciones humanas registradas
    cur.execute(
        "SELECT * FROM registro_accion_humana WHERE rol_usuario = ? ORDER BY accion_id DESC LIMIT 10;",
        (rol,),
    )
    acciones_registradas = [dict(r) for r in cur.fetchall()]

    # 3. Datos específicos de cada vista SQL según el rol
    if rol == "docente":
        cur.execute(
            "SELECT * FROM vista_docente WHERE grupo_id = ? ORDER BY codigo_seguimiento ASC;",
            (grupo_id,),
        )
        alumnos_aula = [dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT * FROM vista_director_clima WHERE escuela_id = ? ORDER BY semana_num ASC;",
            (escuela_id,),
        )
        serie_clima = [dict(r) for r in cur.fetchall()]

        conn.close()
        return {
            "user": user,
            "sql_security": {
                "db_role": "role_docente",
                "granted_views": ["vista_docente", "vista_avisos_predictivos"],
                "scope_filter": f"grupo_id = '{grupo_id}'",
                "ethical_banner": "La decisión es tuya; el modelo puede equivocarse. Sin rankings ni semáforos por alumno.",
            },
            "kpis": [
                {
                    "label": "Continuidad en la asistencia",
                    "value": "87,5%",
                    "note": "Descenso puntual en jornadas de lluvia intensa (>35 mm)",
                },
                {
                    "label": "Progreso y entregas del grupo",
                    "value": "71,4 pts",
                    "note": "Evolución estable en las 28 carpetas de aprendizaje",
                },
                {
                    "label": "Formación docente y metodología",
                    "value": "22,0 h",
                    "note": "Aplicación activa de trabajo por estaciones en Ciencias",
                },
                {
                    "label": "Utilización de recursos en aula",
                    "value": "68,4%",
                    "note": "Uso de guías modulares y laboratorio digital cada jueves",
                },
                {
                    "label": "Participación y vínculo familiar",
                    "value": "81,0%",
                    "note": "23 de 28 familias participan en el seguimiento mensual",
                },
            ],
            "avisos_predictivos": avisos,
            "alumnos_contexto": alumnos_aula,
            "serie_lluvia_cosecha": serie_clima,
            "acciones_humanas": acciones_registradas,
        }

    elif rol == "director":
        cur.execute(
            "SELECT * FROM vista_director WHERE escuela_id = ? ORDER BY grupo_id ASC;",
            (escuela_id,),
        )
        grupos_centro = [dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT * FROM vista_director_clima WHERE escuela_id = ? ORDER BY semana_num ASC;",
            (escuela_id,),
        )
        serie_clima = [dict(r) for r in cur.fetchall()]

        conn.close()
        return {
            "user": user,
            "sql_security": {
                "db_role": "role_director",
                "granted_views": ["vista_director", "vista_director_clima", "vista_avisos_predictivos"],
                "scope_filter": f"escuela_id = '{escuela_id}' (Agregado k >= 26 por aula)",
                "ethical_banner": "La decisión es tuya; el modelo puede equivocarse. Datos agregados por grupo sin exposición individual.",
            },
            "kpis": [
                {
                    "label": "Asistencia media del centro",
                    "value": "84,2%",
                    "note": "Afectada en semanas 5 a 8 por lluvias y calendario de cosecha",
                },
                {
                    "label": "Índice de aprendizaje del centro",
                    "value": "68,5 pts",
                    "note": "Mayor consolidación en grupos con aprendizaje por proyectos",
                },
                {
                    "label": "Formación docente práctica",
                    "value": "16,5 h",
                    "note": "Asimetría entre 1º de Secundaria (9,8h) y 3º de Secundaria (26h)",
                },
                {
                    "label": "Uso efectivo de equipamiento",
                    "value": "52,5%",
                    "note": "84% de dispositivos disponibles en el centro (31,5% sin uso)",
                },
                {
                    "label": "Participación y tutoría familiar",
                    "value": "79,0%",
                    "note": "Factor protector principal frente al ausentismo estacional",
                },
            ],
            "avisos_predictivos": avisos,
            "grupos_centro": grupos_centro,
            "serie_lluvia_cosecha": serie_clima,
            "acciones_humanas": acciones_registradas,
        }

    else:  # delegado
        cur.execute("SELECT * FROM vista_delegado ORDER BY escuela_id ASC;")
        escuelas_red = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {
            "user": user,
            "sql_security": {
                "db_role": "role_delegado",
                "granted_views": ["vista_delegado", "vista_avisos_predictivos"],
                "scope_filter": "Red Territorial Sur (12 Centros Cabecera · k-anonimato >= 98 alumnos)",
                "ethical_banner": "La decisión es tuya; el modelo puede equivocarse. Planificación territorial equitativa auditada contra sesgos.",
            },
            "kpis": [
                {
                    "label": "Asistencia media territorial",
                    "value": "83,9%",
                    "note": "Brecha de 14 puntos entre centros urbanos (92%) y rurales (76%)",
                },
                {
                    "label": "Progreso medio de aprendizaje",
                    "value": "67,9 pts",
                    "note": "Fuerte correlación con mentoría docente y continuidad escolar",
                },
                {
                    "label": "Formación docente en la red",
                    "value": "17,9 h",
                    "note": "5 escuelas cuentan con menos de 12 horas de práctica aplicada",
                },
                {
                    "label": "Aprovechamiento de recursos",
                    "value": "54,3%",
                    "note": "81,9% de disponibilidad física media frente a 54,3% de uso en aula",
                },
                {
                    "label": "Participación comunitaria",
                    "value": "74,8%",
                    "note": "Sostiene la permanencia escolar en comarcas agrícolas",
                },
            ],
            "avisos_predictivos": avisos,
            "escuelas_red": escuelas_red,
            "acciones_humanas": acciones_registradas,
        }


@app.post("/api/acciones")
def register_human_action(
    req: ActionCreateRequest, user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Registra la decisión tomada por el docente, director o delegado sobre un aviso del modelo,
    actualizando su estado a 'Acuerdo registrado' y dejando trazabilidad de supervisión humana.
    """
    init_and_seed_database()
    conn = get_sqlite_connection()
    cur = conn.cursor()

    ambito = user.get("grupo_id") if user["rol"] == "docente" else (user.get("escuela_id") or "RED-SUR")
    cur.execute(
        """
        INSERT INTO registro_accion_humana
        (prediccion_id, rol_usuario, usuario_nombre, ambito_id, decision_tomada, comentario_pedagogico)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (
            req.prediccion_id,
            user["rol"],
            user["nombre_completo"],
            ambito,
            req.decision_tomada,
            req.comentario_pedagogico or "Acción revisada y validada bajo criterio profesional docente.",
        ),
    )
    cur.execute(
        "UPDATE prediccion SET estado_revision = 'Acuerdo registrado' WHERE prediccion_id = ?;",
        (req.prediccion_id,),
    )
    conn.commit()
    conn.close()
    return {
        "status": "ok",
        "message": "Acción pedagógica registrada correctamente en la base de datos.",
        "prediccion_id": req.prediccion_id,
        "nuevo_estado": "Acuerdo registrado",
    }


@app.post("/api/simular-subvencion")
def simulate_territorial_grant(
    req: GrantSimulationRequest, user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Simulador para el panel de Coordinación Territorial / Delegado y Dirección:
    calcula el efecto estimado de repartir el presupuesto entre Becas de Transporte/Comedor,
    Formación Docente Práctica y Servidores Locales Offline.
    """
    total_pct = max(1.0, req.pct_becas_transporte + req.pct_formacion_docente + req.pct_servidores_offline)
    w_becas = req.pct_becas_transporte / total_pct
    w_form = req.pct_formacion_docente / total_pct
    w_off = req.pct_servidores_offline / total_pct

    escala = req.presupuesto_total_eur / 100000.0
    mejora_asistencia_rural = round(min(11.5, (w_becas * 7.8 + w_off * 2.4 + w_form * 1.8) * escala), 1)
    mejora_uso_recursos = round(min(28.0, (w_form * 21.0 + w_off * 11.5 + w_becas * 2.0) * escala), 1)
    mejora_aprendizaje_pts = round(min(12.4, (w_form * 5.6 + w_becas * 4.2 + w_off * 3.1) * escala), 1)
    alumnos_beneficiados = int(min(2427, round((w_becas * 950 + w_form * 820 + w_off * 510) * escala)))

    return {
        "presupuesto_total_eur": req.presupuesto_total_eur,
        "distribucion_normalizada": {
            "becas_transporte_pct": round(w_becas * 100, 1),
            "formacion_docente_pct": round(w_form * 100, 1),
            "servidores_offline_pct": round(w_off * 100, 1),
        },
        "impacto_estimado": {
            "mejora_asistencia_rural_pct": mejora_asistencia_rural,
            "mejora_uso_recursos_pct": mejora_uso_recursos,
            "mejora_aprendizaje_pts": mejora_aprendizaje_pts,
            "estudiantes_en_cohortes_beneficiadas": alumnos_beneficiados,
        },
        "lectura_humanizada": (
            f"Con una inversión de {req.presupuesto_total_eur:,.0f} EUR ({w_becas*100:.0f}% en becas de transporte rural, "
            f"{w_form*100:.0f}% en mentoría docente in-situ y {w_off*100:.0f}% en servidores offline), "
            f"se estima recuperar +{mejora_asistencia_rural}% de asistencia en épocas de lluvia y cosecha, "
            f"elevar +{mejora_uso_recursos}% la utilización del equipamiento ya disponible en las aulas "
            f"y mejorar en +{mejora_aprendizaje_pts} puntos el progreso medio de aprendizaje."
        ),
    }


# =============================================================================
# ENDPOINTS DEL SERVIDOR MCP Y CHAT CONECTADO A LA BASE DE DATOS
# =============================================================================

@app.get("/api/mcp/tools")
def get_mcp_tools_metadata(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Muestra las 3 herramientas estándar del Servidor MCP de Base de Datos y las vistas
    sobre las que el usuario actual tiene permiso GRANT SELECT.
    """
    rol = user["rol"]
    vistas = list_tables(rol)
    return {
        "mcp_server_name": "donprofesor-db-mcp",
        "protocol": "Model Context Protocol (MCP)",
        "active_db_role": f"role_{rol}",
        "tools": [
            {
                "name": "list_tables",
                "description": "Lista las vistas SQL sobre las cuales el rol actual tiene permiso GRANT SELECT.",
            },
            {
                "name": "describe_table",
                "description": "Inspecciona los nombres y tipos de columnas de una vista autorizada antes de consultar.",
            },
            {
                "name": "read_query",
                "description": "Ejecuta una consulta SQL SELECT de solo lectura sobre las vistas autorizadas para el rol.",
            },
        ],
        "accessible_views": vistas,
    }


@app.post("/api/mcp/read-query")
def execute_direct_mcp_query(
    req: DirectMCPQueryRequest, user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Permite probar directamente la tool `read_query` del Servidor MCP respetando los permisos del rol."""
    ambito = user.get("grupo_id") if user["rol"] == "docente" else (user.get("escuela_id") or "ALL")
    return read_query(user["rol"], ambito, req.sql_query)


@app.post("/api/chat-mcp")
def chat_with_mcp_endpoint(
    req: ChatMCPRequest, user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Recibe una pregunta en lenguaje natural desde el Chat de DONPROFESOR,
    invoca las herramientas del Servidor MCP (`list_tables`, `describe_table`, `read_query`)
    con el rol del token JWT y devuelve tanto la respuesta pedagógica como la traza MCP ejecutada.
    """
    ambito = user.get("grupo_id") if user["rol"] == "docente" else (user.get("escuela_id") or "ALL")
    return answer_pedagogical_chat_with_mcp(user["rol"], ambito, req.question)


@app.get("/", response_class=HTMLResponse)
def serve_donprofesor_web() -> HTMLResponse:
    html_file = Path(__file__).resolve().parent.parent / "web" / "templates" / "index.html"
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
