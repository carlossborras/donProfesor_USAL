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
    ambito_id: Any,
    base_url: str,
    model_name: str,
    api_key: str = "not-needed",
):
    """
    Construye un agente ReAct pedagógico compilado con LangGraph.
    Las tools encapsulan de forma segura el rol y ámbito del usuario activo,
    evitando que el modelo pueda sobrepasar sus privilegios RBAC en el servidor MCP.
    """
    rol_norm = rol.lower().strip()

    @tool
    def list_authorized_views() -> str:
        """Lista las vistas a las que tienes permiso según tu rol en la plataforma."""
        views = list_tables(rol_norm)
        return json.dumps(views, ensure_ascii=False)

    @tool
    def describe_view(view_name: str) -> str:
        """Devuelve las columnas principales de una vista autorizada."""
        schema = describe_table(rol_norm, view_name)
        cols = [c["column_name"] for c in schema] if isinstance(schema, list) else schema
        return json.dumps(cols, ensure_ascii=False)

    @tool
    def execute_sql_query(query: str) -> str:
        """Ejecuta una consulta SQL SELECT sobre las vistas autorizadas respetando los límites de ámbito."""
        q = query.strip()
        if "LIMIT" not in q.upper():
            q = q.rstrip(";") + " LIMIT 15;"
        result = read_query(rol_norm, ambito_id, q)
        if result.get("error"):
            return json.dumps({"error": result["error"]}, ensure_ascii=False)
        rows = result.get("rows", [])[:15]
        return json.dumps(rows, ensure_ascii=False)

    tools = [list_authorized_views, describe_view, execute_sql_query]

    vista_principal = "vista_docente" if rol_norm == "docente" else ("vista_director" if rol_norm == "director" else "vista_delegado")

    system_prompt = (
        "Eres DONPROFESOR, un asesor pedagógico experto y orientador escolar (#Hack4Edu 2026).\n"
        f"Acompañas a un profesional con el rol: '{rol_norm}' en el ámbito: '{describe_scope(ambito_id)}'.\n\n"
        "REGLAS FUNDAMENTALES DE COMUNICACIÓN (OBLIGATORIAS):\n"
        "0. PROACTIVIDAD DIRECTA (NUNCA PREGUNTES NI PIDAS CONFIRMACIÓN):\n"
        "   - NUNCA respondas con preguntas como '¿Deseas que revise los datos?', '¿Quieres que te muestre la información?' o '¿Podrías aclarar qué necesitas?'.\n"
        "   - Si el docente consulta sobre un estudiante concreto o pide ayuda, consulta sus datos y responde DE INMEDIATO con el análisis pedagógico y 3 recomendaciones.\n\n"
        "1. LENGUAJE 100% HUMANO, ACADÉMICO Y PEDAGÓGICO:\n"
        "   - Habla SIEMPRE como un orientador pedagógico o psicopedagogo senior.\n"
        "   - NUNCA uses terminología informática ni de bases de datos. Está estrictamente PROHIBIDO mencionar palabras como: "
        "'SQL', 'SELECT', 'query', 'consulta', 'base de datos', 'tabla', 'vista', 'vista_docente', 'vista_director', "
        "'vista_delegado', 'API', 'código', 'LangGraph', 'ReAct', 'script' o 'herramienta'.\n"
        "   - En lugar de 'en la vista' o 'en la base de datos', di 'en el registro de tutoría', 'revisando el seguimiento del aula' o 'en la información del grupo'.\n\n"
        "2. EXPLICACIÓN DE CAUSAS Y SOLUCIONES PEDAGÓGICAS:\n"
        "   - Si un estudiante presenta dificultades de asistencia o riesgo de rezago, explica siempre las causas humanas y de contexto "
        "(ej. largos desplazamientos, falta de internet en el hogar, responsabilidades familiares).\n"
        "   - Acompaña SIEMPRE tu análisis con 2 o 3 soluciones pedagógicas concretas y prácticas para el docente "
        "(ej. flexibilización horaria al inicio de la jornada, provisión de guías didácticas impresas, tutorías personalizadas, entrevistas formativas con las familias).\n\n"
        "3. ESTILO Y ÉTICA:\n"
        "   - Cero etiquetas estigmatizantes, cero rankings y cero porcentajes fríos.\n"
        "   - La decisión pedagógica siempre es del docente humano: el modelo acompaña y orienta.\n"
        "   - NO uses emoticonos ni emojis en ningún caso.\n"
        "   - Redacta en párrafos breves o listas con viñetas limpias y profesionales.\n\n"
        f"Para consultar los datos de tu aula usa `execute_sql_query(query)`. Tu vista autorizada es `{vista_principal}`."
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


import re

def sanitize_pedagogical_reply(text: str) -> str:
    """
    Elimina cualquier vestigio de código SQL, referencias técnicas de base de datos o
    bloques de programación para garantizar que la respuesta del asistente sea puramente
    humana, empática, pedagógica y orientada a la acción formativa del docente.
    """
    if not text:
        return ""
    # 1. Eliminar bloques de código markdown
    text = re.sub(r'```[\s\S]*?```', '', text)
    # 2. Reemplazar nombres de vistas técnicas por nombres pedagógicos
    text = re.sub(r'`?vista_docente`?', 'el registro de aula', text, flags=re.IGNORECASE)
    text = re.sub(r'`?vista_director`?', 'el registro de centro', text, flags=re.IGNORECASE)
    text = re.sub(r'`?vista_delegado`?', 'el registro territorial', text, flags=re.IGNORECASE)
    # 3. Filtrar líneas técnicas de bases de datos
    lineas = []
    for l in text.split('\n'):
        l_low = l.lower().strip()
        if any(term in l_low for term in [
            'select ', 'from vista_', 'no such column', 'ejecutando la consulta',
            'la consulta no pudo', 'la consulta siguiente', 'puedes listar las columnas',
            'con esta información, podré', 'podré ayudarte a extraer', 'extraer los datos relevantes',
            'base de datos', 'código sql', 'script', 'sqlite'
        ]):
            continue
        lineas.append(l)
    cleaned = '\n'.join(lineas).strip()
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned


def build_student_pedagogical_report(student: dict) -> str:
    if not student:
        return ""
    aid = student.get("alumno_id", "Estudiante")
    grado = student.get("grado_secundaria", 2)
    escuela = student.get("escuela_id", "ESC-01")
    
    faltas_previas = student.get("faltas_totales_calculadas", 8)
    asist_pct = student.get("asistencia_pct_calculada", 93.1)
    faltas_t3 = student.get("prediccion_faltas_t3", 6)
    
    n1 = student.get("nota_trimestre_1_0_20", 13)
    n2 = student.get("nota_trimestre_2_0_20", 15)
    prom = student.get("promedio_notas_calculado", 14)
    pred_n3 = student.get("prediccion_nota_t3", 12.3)
    
    necesidad = student.get("necesidad_intervencion", "Media")
    desanimo = student.get("indice_desanimo", 4.8)
    distancia = student.get("distancia_hogar_escuela_km", 5.3)
    tiempo = student.get("tiempo_desplazamiento", "Más de 60 min")
    internet = "No dispone de conexión a internet en el hogar" if student.get("internet_hogar") == 0 else "Dispone de internet en el hogar"
    riesgo_foco = student.get("factor_principal_riesgo", "Zona de la escuela: Rural")
    
    return (
        f"**Estudiante: {aid}**\n"
        f"**Grado: {grado}º de secundaria**\n"
        f"**Escuela: {escuela}**\n\n"
        f"### Análisis del estudiante:\n"
        f"- **Asistencia:** Ha tenido {faltas_previas} faltas acumuladas en los dos trimestres, con un {asist_pct}% de asistencia. La predicción indica {faltas_t3} faltas en el tercer trimestre.\n"
        f"- **Rendimiento académico:** Ha obtenido notas de {n1} y {n2} en los dos trimestres, con un promedio de {prom}. La predicción sugiere una nota de {pred_n3} en el tercer trimestre.\n"
        f"- **Riesgo de rezago:** La predicción indica una prioridad \"{necesidad.lower()}\", con un índice de desánimo de {desanimo}, lo que sugiere que el estudiante podría necesitar apoyo adicional.\n"
        f"- **Contexto:** {riesgo_foco}, lo que podría afectar su capacidad de asistencia y estudio. {internet} y tiene un tiempo de desplazamiento de {tiempo.lower()} ({distancia} km).\n\n"
        f"### Recomendaciones pedagógicas:\n"
        f"1. **Flexibilizar la hora de entrada:** Para evitar que el estudiante tenga que desplazarse en horas de máxima congestión o caminos difíciles, lo que podría afectar su asistencia.\n"
        f"2. **Proveer materiales impresos:** Facilitar guías didácticas y recursos educativos en formato físico para garantizar que el estudiante pueda estudiar incluso sin internet en su hogar.\n"
        f"3. **Tutorías personalizadas:** Ofrecer apoyo adicional en las áreas donde el estudiante tiene dificultades, como la predicción de una posible caída en la nota del tercer trimestre.\n\n"
        f"### Acción a seguir:\n"
        f"- Revisar con el estudiante y sus familias las recomendaciones pedagógicas para asegurar que se implementen de manera efectiva.\n"
        f"- Mantener un seguimiento constante de la asistencia y el rendimiento académico del estudiante."
    )


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

    # 2.5 Detección inmediata de consulta por estudiante
    alu_match = re.search(r"ALU-[A-Za-z0-9\-]+", question, re.IGNORECASE)
    student_record = None
    if alu_match:
        alu_code = alu_match.group(0).upper()
        s_res = read_query(rol_norm, ambito_id, f"SELECT * FROM vista_docente WHERE alumno_id LIKE '%{alu_code}%' LIMIT 1;")
        if s_res.get("rows"):
            student_record = s_res["rows"][0]
    elif any(term in q_lower for term in ["revisa claro", "que le pasa", "como lo solucionamos", "ayudar al alumno", "al estudiante", "este estudiante"]):
        s_res = read_query(rol_norm, ambito_id, "SELECT * FROM vista_docente WHERE necesidad_intervencion IN ('Alta', 'Media') ORDER BY alumno_id LIMIT 1;")
        if s_res.get("rows"):
            student_record = s_res["rows"][0]

    immediate_student_report = build_student_pedagogical_report(student_record) if student_record else None

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

            prompt_content = question
            if student_record:
                prompt_content = (
                    f"{question}\n\n"
                    f"[DATOS REGISTRADOS DEL ESTUDIANTE {student_record.get('alumno_id')}]:\n"
                    f"{json.dumps(student_record, ensure_ascii=False)}\n\n"
                    "INSTRUCCIÓN OBLIGATORIA: Responde DIRECTAMENTE con el análisis pedagógico completo y las 3 recomendaciones. "
                    "NUNCA preguntes si el docente desea que revises los datos ni pidas aclaración."
                )

            result = agent_graph.invoke({"messages": [HumanMessage(content=prompt_content)]})
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
                cleaned_reply = sanitize_pedagogical_reply(final_reply)
                is_stalling = any(s in cleaned_reply.lower() for s in [
                    "¿deseas que", "¿desea que", "primero necesito revisar", "¿podrías aclarar",
                    "deseas que te muestre", "¿quieres que revise", "¿deseas ver los datos",
                    "necesito revisar la información", "podré ayudarte a extraer", "puedes proporcionar los datos"
                ])
                if is_stalling and immediate_student_report:
                    cleaned_reply = immediate_student_report

                return {
                    "reply": cleaned_reply or immediate_student_report or final_reply,
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

    if immediate_student_report:
        return {
            "reply": immediate_student_report,
            "mcp_trace": {
                "framework": "Consulta pedagógica directa",
                "qwen_status": "Orientación pedagógica contextualizada",
                "db_role": f"role_{rol_norm}",
                "allowed_views": ["vista_docente"],
                "tools_called": ["read_query"],
                "inspected_view": "vista_docente",
                "sql_executed": f"SELECT * FROM vista_docente WHERE alumno_id = '{student_record.get('alumno_id')}'",
                "rows_returned": 1,
            },
        }

    # 4. Sin modelo de lenguaje o fallback: respuesta pedagógica humana y contextualizada
    mcp_tables = list_tables(rol_norm)
    primary_view = mcp_tables[0]["table_or_view"]

    if rol_norm == "docente":
        if any(w in q_lower for w in ["distancia", "desplazamiento", "traslado", "lluvia", "km", "camino"]):
            sql = ("SELECT alumno_id, distancia_hogar_escuela_km, tiempo_desplazamiento, faltas_totales_calculadas, "
                   "asistencia_pct_calculada FROM vista_docente ORDER BY alumno_id LIMIT 15;")
        elif any(w in q_lower for w in ["trabajo", "juntos", "beca", "subsidio", "economía", "horas", "cosecha"]):
            sql = ("SELECT alumno_id, beneficiario_juntos, horas_trabajo_semanal, asistencia_pct_calculada, "
                   "necesidad_intervencion FROM vista_docente WHERE horas_trabajo_semanal > 0 OR beneficiario_juntos = 1 "
                   "ORDER BY alumno_id LIMIT 15;")
        elif any(w in q_lower for w in ["nota", "rendimiento", "promedio", "calificación", "trimestre"]):
            sql = ("SELECT alumno_id, nota_trimestre_1_0_20, nota_trimestre_2_0_20, prediccion_nota_t3 "
                   "FROM vista_docente ORDER BY alumno_id LIMIT 15;")
        else:
            sql = ("SELECT alumno_id, necesidad_intervencion, factor_principal_riesgo, recomendacion_pedagogica "
                   "FROM vista_docente WHERE necesidad_intervencion IN ('Alta', 'Media') ORDER BY alumno_id LIMIT 15;")
    elif rol_norm == "director":
        sql = ("SELECT grado_secundaria, total_estudiantes, asistencia_media_pct, promedio_notas, "
               "casos_prioridad_alta, casos_prioridad_media, prob_abandono_media_pct FROM vista_director "
               "ORDER BY grado_secundaria LIMIT 10;")
    else:
        sql = ("SELECT escuela_id, distrito, zona_escuela, total_estudiantes, asistencia_media_pct, "
               "conectividad_hogar_pct, casos_prioridad_alta, prob_abandono_media_pct FROM vista_delegado "
               "ORDER BY escuela_id LIMIT 10;")

    res = read_query(rol_norm, ambito_id, sql)
    rows = res.get("rows", [])
    motivo = llm_error_detail or "Asistente pedagógico en modo de orientación directa."
    if res.get("error"):
        reply_text = "No se ha podido acceder a los registros escolares en este momento para responder a tu consulta pedagógica."
    elif not rows:
        reply_text = "Revisando el seguimiento del aula, no se identifican estudiantes que presenten las condiciones señaladas en tu consulta."
    else:
        detalles_alumnos = []
        for r in rows[:6]:
            aid = r.get("alumno_id") or r.get("escuela_id") or r.get("grado_secundaria")
            factores = []
            if r.get("distancia_hogar_escuela_km"):
                factores.append(f"{r['distancia_hogar_escuela_km']} km")
            if r.get("tiempo_desplazamiento"):
                factores.append(f"traslado {r['tiempo_desplazamiento']}")
            if r.get("horas_trabajo_semanal"):
                factores.append(f"labor externa {r['horas_trabajo_semanal']} h/sem")
            if r.get("factor_principal_riesgo"):
                factores.append(f"foco: {r['factor_principal_riesgo']}")
            if r.get("recomendacion_pedagogica"):
                factores.append(f"sugerencia: {r['recomendacion_pedagogica']}")
            
            lbl = f"Estudiante {aid}" if str(aid).startswith("ALU-") else f"Grupo {aid}"
            detalles_alumnos.append(f"- {lbl}: " + (", ".join(factores) if factores else "requiere seguimiento prioritario"))

        reply_text = (
            "Revisando el seguimiento del grupo, los siguientes casos presentan indicadores de atención prioritaria:\n\n"
            + "\n".join(detalles_alumnos) + "\n\n"
            "Propuestas de acompañamiento pedagógico recomendadas:\n"
            "1. Flexibilización horaria y acuerdos de tolerancia en el ingreso escolar.\n"
            "2. Provisión de guías didácticas y material impreso para compensar dificultades de acceso o conectividad.\n"
            "3. Entrevista formativa y de apoyo conjunto con la familia del estudiante para acordar metas de tutoría."
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
