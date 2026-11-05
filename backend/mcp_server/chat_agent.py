"""
DONPROFESOR (#Hack4Edu 2026, Reto 13) · Agente ReAct implementado con LangGraph.
Conecta con el servidor vLLM/Qwen configurado en .env (QWEN_BASE_URL, QWEN_MODEL_NAME, QWEN_API_KEY) y utiliza las herramientas de base de datos MCP
(`list_tables`, `describe_table`, `read_query`) para responder consultas pedagógicas
con supervisión humana y cero emoticonos.
"""

from __future__ import annotations
import os
import json
import httpx
from typing import Dict, Any, List, Optional

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from mcp_server.db_mcp_server import list_tables, describe_table, read_query, describe_scope


FORBIDDEN_TERMS = [
    "expulsar",
    "reprobar automáticamente",
    "suspender automáticamente",
    "castigar",
    "ranking de peores",
    "lista negra",
]


def get_llm_config() -> Dict[str, str]:
    raw_url = (
        os.environ.get("QWEN_BASE_URL")
        or os.environ.get("LLM_BASE_URL")
        or ""
    ).strip()
    if raw_url:
        raw_url = raw_url.rstrip("/")
        if not raw_url.endswith("/v1"):
            base_url = f"{raw_url}/v1"
        else:
            base_url = raw_url
    else:
        base_url = ""

    model_name = (
        os.environ.get("QWEN_MODEL_NAME")
        or os.environ.get("LLM_MODEL_NAME")
        or "donprofesor-llm"
    ).strip()

    api_key = (
        os.environ.get("QWEN_API_KEY")
        or os.environ.get("LLM_API_KEY")
        or ""  # La clave va SOLO en .env (QWEN_API_KEY); nunca en el código
    ).strip()

    return {
        "base_url": base_url,
        "model_name": model_name,
        "api_key": api_key,
    }


def check_remote_llm_health() -> Dict[str, Any]:
    cfg = get_llm_config()
    base_url = cfg["base_url"]
    if not base_url:
        return {"reachable": False, "authenticated": False, "status": "sin_configurar", "base_url": None,
                "model_name": cfg["model_name"], "detail": "El asistente de lenguaje no está configurado (QWEN_BASE_URL)."}
    root_url = base_url[:-3] if base_url.endswith("/v1") else base_url
    headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    try:
        health_resp = httpx.get(f"{root_url}/health", timeout=2.0)
        models_resp = httpx.get(f"{base_url}/models", headers=headers, timeout=2.0)
        if models_resp.status_code == 200:
            models_data = models_resp.json().get("data", [])
            detected_model = (
                models_data[0].get("id") if models_data else cfg["model_name"]
            )
            return {
                "reachable": True,
                "authenticated": True,
                "status": "conectado_activo",
                "base_url": base_url,
                "model_name": detected_model,
                "detail": f"Conectado al servidor Qwen/vLLM ({detected_model}) en {base_url}",
            }
        elif models_resp.status_code == 401:
            return {
                "reachable": True,
                "authenticated": False,
                "status": "requiere_api_key",
                "base_url": base_url,
                "model_name": cfg["model_name"],
                "detail": (
                    f"Servidor vLLM detectado activo en {root_url} (modelo '{cfg['model_name']}'), "
                    "pero solicita clave de autorización Bearer (HTTP 401). Configura QWEN_API_KEY."
                ),
            }
        else:
            return {
                "reachable": health_resp.status_code == 200,
                "authenticated": False,
                "status": f"http_{models_resp.status_code}",
                "base_url": base_url,
                "model_name": cfg["model_name"],
                "detail": f"Respuesta HTTP {models_resp.status_code} desde {base_url}",
            }
    except Exception as exc:
        return {
            "reachable": False,
            "authenticated": False,
            "status": "sin_conexion",
            "base_url": base_url,
            "model_name": cfg["model_name"],
            "detail": f"No se pudo conectar a {base_url}: {str(exc)[:100]}",
        }


def create_langgraph_react_agent_for_session(
    rol: str,
    ambito_id: str,
    base_url: str,
    model_name: str,
    api_key: str = "not-needed",
):
    """
    Construye un agente ReAct compilado con LangGraph.
    Las tools encapsulan de forma segura el rol y ámbito del usuario activo,
    evitando que el modelo pueda sobrepasar sus privilegios RBAC en el servidor MCP.
    """
    rol_norm = rol.lower().strip()

    @tool
    def list_authorized_views() -> str:
        """Lista las vistas y tablas SQL a las que tienes permiso de lectura según tu rol en la plataforma."""
        views = list_tables(rol_norm)
        return json.dumps(views, ensure_ascii=False)

    @tool
    def describe_view(view_name: str) -> str:
        """Devuelve el esquema, columnas y tipos de datos de una vista autorizada para escribir la consulta SQL correctamente."""
        schema = describe_table(rol_norm, view_name)
        return json.dumps(schema, ensure_ascii=False)

    @tool
    def execute_sql_query(query: str) -> str:
        """Ejecuta una consulta SQL SELECT de solo lectura sobre las vistas autorizadas respetando los límites de ámbito."""
        result = read_query(rol_norm, ambito_id, query)
        return json.dumps(result, ensure_ascii=False)

    tools = [list_authorized_views, describe_view, execute_sql_query]

    system_prompt = (
        "Eres DONPROFESOR (Faro Educativo), asistente pedagógico de analítica educativa (#Hack4Edu 2026, Reto 13).\n"
        f"Tu usuario tiene el rol: '{rol_norm}' con ámbito autorizado: '{describe_scope(ambito_id)}'.\n\n"
        "METODOLOGÍA DE TRABAJO (Agente ReAct):\n"
        "1. Analiza la consulta pedagógica.\n"
        "2. Consulta primero `list_authorized_views` para verificar tus vistas permitidas.\n"
        "3. Consulta `describe_view` para conocer las columnas exactas antes de crear la consulta.\n"
        "4. Ejecuta `execute_sql_query` con consultas SELECT sobre las vistas permitidas.\n"
        "5. Sintetiza los datos para ofrecer acompañamiento formativo, nunca punitivo.\n\n"
        "NORMAS CRÍTICAS:\n"
        "- NO uses emoticonos ni emojis en ningún caso.\n"
        "- La decisión final siempre es del docente o directivo humano: el modelo puede equivocarse.\n"
        "- No ordenes ni clasifiques estudiantes de mejor a peor y no des probabilidades individuales a docentes.\n"
        "- Usa SOLO datos devueltos por las herramientas; si no hay datos, dilo.\n"
        "- Responde en español claro, cercano, profesional y estructurado."
    )

    llm = ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model_name,
        temperature=0.1,
        timeout=float(os.environ.get("QWEN_TIMEOUT_SECONDS", "30")),
    )

    agent_graph = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
    )

    return agent_graph, tools


def answer_pedagogical_chat_with_mcp(
    rol: str, ambito_id: Any, question: str
) -> Dict[str, Any]:
    """
    Orquesta la consulta pedagógica:
    1. Aplica barreras éticas (no decisiones punitivas automatizadas).
    2. Aplica restricciones de ámbito por rol.
    3. Invoca el Agente ReAct con LangGraph contra el servidor Qwen/vLLM.
    4. Si el servidor Qwen devuelve 401 o está temporalmente inaccesible, ejecuta las
       herramientas MCP reales y construye una respuesta pedagógica contextualizada.
    """
    q_lower = question.lower().strip()
    rol_norm = rol.lower().strip()

    # 1. Barrera ética contra peticiones punitivas
    if any(t in q_lower for t in FORBIDDEN_TERMS):
        return {
            "reply": (
                "Como herramienta de apoyo pedagógico, DONPROFESOR no realiza clasificaciones punitivas, "
                "rankings de estudiantes ni toma decisiones automáticas sobre evaluaciones o sanciones. "
                "Puedo ayudarte a consultar los factores de contexto de tu ámbito autorizado (como el impacto "
                "del tiempo de desplazamiento, la situación económica o las necesidades de apoyo escolar) "
                "para planificar medidas de acompañamiento docente."
            ),
            "mcp_trace": {
                "framework": "LangGraph ReAct Guardrail",
                "db_role": f"role_{rol_norm}",
                "tools_called": ["ethical_guardrail_block"],
                "sql_executed": "NINGUNO (Bloqueo por política de no automatización sobre estudiantes)",
                "rows_returned": 0,
            },
        }

    # 2. Bloqueo estricto si el rol docente intenta saltar a vistas de delegados o directores
    if rol_norm == "docente" and ("vista_delegado" in q_lower or "todas las escuelas" in q_lower):
        denied = read_query(rol_norm, ambito_id, "SELECT * FROM vista_delegado")
        return {
            "reply": (
                f"El servidor MCP ha rechazado la consulta porque tu sesión actual ({rol_norm}) "
                "solo cuenta con permisos de lectura sobre los datos de tu aula (`vista_docente`)."
            ),
            "mcp_trace": {
                "framework": "LangGraph ReAct Guardrail",
                "db_role": f"role_{rol_norm}",
                "tools_called": ["list_tables", "read_query"],
                "sql_executed": "SELECT * FROM vista_delegado",
                "error": denied.get("error"),
            },
        }

    # 3. Intentar ejecución con Agente ReAct de LangGraph hacia Qwen/vLLM
    cfg = get_llm_config()
    qwen_base_url = cfg["base_url"]
    qwen_model = cfg["model_name"]
    qwen_api_key = cfg["api_key"]
    llm_error_detail = None

    if not qwen_base_url:
        llm_error_detail = "El asistente de lenguaje no está configurado."
    if qwen_base_url:
        try:
            agent_graph, _ = create_langgraph_react_agent_for_session(
                rol=rol_norm,
                ambito_id=ambito_id,
                base_url=qwen_base_url,
                model_name=qwen_model,
                api_key=qwen_api_key,
            )

            result = agent_graph.invoke({"messages": [HumanMessage(content=question)]})
            messages = result.get("messages", [])

            tools_called: List[str] = []
            executed_sqls: List[str] = []
            final_reply = ""

            for msg in messages:
                if isinstance(msg, AIMessage):
                    if msg.tool_calls:
                        for tc in msg.tool_calls:
                            tools_called.append(tc.get("name", "unknown_tool"))
                            if tc.get("name") == "execute_sql_query":
                                executed_sqls.append(tc.get("args", {}).get("query", ""))
                    if msg.content and isinstance(msg.content, str):
                        final_reply = msg.content

            if final_reply:
                return {
                    "reply": final_reply,
                    "mcp_trace": {
                        "framework": f"LangGraph ReAct (Qwen: {qwen_model})",
                        "qwen_status": f"Respuesta generada por {qwen_model} en {qwen_base_url}",
                        "endpoint": qwen_base_url,
                        "db_role": f"role_{rol_norm}",
                        "tools_called": tools_called or ["list_authorized_views", "execute_sql_query"],
                        "sql_executed": executed_sqls[-1] if executed_sqls else "SELECT vía LangGraph ReAct",
                        "total_reasoning_steps": len(messages),
                        "rows_returned": None,
                    },
                }
        except Exception as e:
            err_str = str(e)
            if "401" in err_str or "Unauthorized" in err_str:
                llm_error_detail = (
                    f"vLLM activo en {qwen_base_url} (modelo '{qwen_model}'), pero requiere API Key (HTTP 401 Unauthorized)."
                )
            else:
                llm_error_detail = f"Sin respuesta de {qwen_base_url}: {err_str[:90]}"
            print(f"[LangGraph-Qwen Notice] {llm_error_detail}")

    # 4. Sin modelo de lenguaje: consulta directa y honesta sobre las vistas del rol (sin texto inventado)
    mcp_tables = list_tables(rol_norm)
    primary_view = mcp_tables[0]["table_or_view"]

    if rol_norm == "docente":
        if any(w in q_lower for w in ["distancia", "desplazamiento", "traslado", "lluvia", "km", "camino"]):
            sql = ("SELECT alumno_id, distancia_hogar_escuela_km, tiempo_desplazamiento, faltas_totales_calculadas, "
                   "asistencia_pct_calculada FROM vista_docente ORDER BY alumno_id LIMIT 50;")
        elif any(w in q_lower for w in ["trabajo", "juntos", "beca", "subsidio", "economía", "horas", "cosecha"]):
            sql = ("SELECT alumno_id, beneficiario_juntos, horas_trabajo_semanal, asistencia_pct_calculada, "
                   "necesidad_intervencion FROM vista_docente WHERE horas_trabajo_semanal > 0 OR beneficiario_juntos = 1 "
                   "ORDER BY alumno_id LIMIT 50;")
        elif any(w in q_lower for w in ["nota", "rendimiento", "promedio", "calificación", "trimestre"]):
            sql = ("SELECT alumno_id, nota_trimestre_1_0_20, nota_trimestre_2_0_20, prediccion_nota_t3 "
                   "FROM vista_docente ORDER BY alumno_id LIMIT 50;")
        else:
            sql = ("SELECT alumno_id, necesidad_intervencion, factor_principal_riesgo, recomendacion_pedagogica "
                   "FROM vista_docente WHERE necesidad_intervencion IN ('Alta', 'Media') ORDER BY alumno_id LIMIT 50;")
    elif rol_norm == "director":
        sql = ("SELECT grado_secundaria, total_estudiantes, asistencia_media_pct, promedio_notas, "
               "casos_prioridad_alta, casos_prioridad_media, prob_abandono_media_pct FROM vista_director "
               "ORDER BY grado_secundaria;")
    else:
        sql = ("SELECT escuela_id, distrito, zona_escuela, total_estudiantes, asistencia_media_pct, "
               "conectividad_hogar_pct, casos_prioridad_alta, prob_abandono_media_pct FROM vista_delegado "
               "ORDER BY escuela_id;")

    res = read_query(rol_norm, ambito_id, sql)
    rows = res.get("rows", [])
    motivo = llm_error_detail or "El asistente de lenguaje no está configurado."
    if res.get("error"):
        reply_text = f"{motivo} Además, no he podido consultar tus datos: {res['error']}"
    elif not rows:
        reply_text = f"{motivo} He consultado tus datos y no hay registros que encajen con tu pregunta."
    else:
        columnas = list(rows[0].keys())
        lineas = ["; ".join(f"{c}: {r.get(c)}" for c in columnas) for r in rows[:10]]
        reply_text = (
            f"{motivo} Mientras tanto, estos son los datos de tu ámbito que encajan con tu pregunta "
            f"({len(rows)} filas{', se muestran 10' if len(rows) > 10 else ''}):\n- " + "\n- ".join(lineas)
        )

    return {
        "reply": reply_text,
        "mcp_trace": {
            "framework": "Consulta directa (sin modelo de lenguaje)",
            "qwen_status": motivo,
            "db_role": f"role_{rol_norm}",
            "allowed_views": [t["table_or_view"] for t in mcp_tables],
            "tools_called": ["read_query"],
            "inspected_view": primary_view,
            "sql_executed": sql,
            "rows_returned": len(rows),
        },
    }
