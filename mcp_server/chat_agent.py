"""
DONPROFESOR (#Hack4Edu 2026, Reto 13) · Agente de Chat Pedagógico conectado al Servidor MCP.
Usa las 3 herramientas estándar del Servidor MCP (`list_tables`, `describe_table`, `read_query`)
para consultar en tiempo real las vistas SQL permitidas para el rol activo y generar una
respuesta en lenguaje humano, sin emoticonos y garantizando supervisión docente.
"""

from __future__ import annotations
import os
import json
from typing import Dict, Any, List
from mcp_server.db_mcp_server import list_tables, describe_table, read_query


def answer_pedagogical_chat_with_mcp(
    rol: str, ambito_id: str, question: str
) -> Dict[str, Any]:
    """
    Orquesta la consulta del usuario pasando siempre por las 3 tools del Servidor MCP:
    1. list_tables(rol)
    2. describe_table(rol, vista)
    3. read_query(rol, ambito_id, sql)
    """
    q_lower = question.lower().strip()
    rol_norm = rol.lower().strip()

    # Paso 1 MCP: Descubrir las vistas disponibles para este rol
    mcp_tables = list_tables(rol_norm)
    primary_view = mcp_tables[0]["table_or_view"]
    mcp_schema = describe_table(rol_norm, primary_view)

    # Guardia ética ante peticiones de decisiones automáticas punitivas
    forbidden_terms = [
        "expulsar",
        "reprobar automáticamente",
        "suspender automáticamente",
        "castigar",
        "ranking de peores",
        "lista negra",
    ]
    if any(t in q_lower for t in forbidden_terms):
        return {
            "reply": (
                "Como herramienta de apoyo pedagógico, DONPROFESOR no realiza clasificaciones punitivas, "
                "rankings de estudiantes ni toma decisiones automáticas sobre evaluaciones o sanciones. "
                "Puedo ayudarte a consultar los factores de contexto de tu ámbito autorizado (como el impacto "
                "del tiempo de desplazamiento, la situación económica o las necesidades de apoyo escolar) "
                "para planificar medidas de acompañamiento docente."
            ),
            "mcp_trace": {
                "db_role": f"role_{rol_norm}",
                "tools_called": ["list_tables", "ethical_guardrail_block"],
                "sql_executed": "NINGUNO (Bloqueo por política de no automatización sobre estudiantes)",
                "rows_returned": 0,
            },
        }

    # Bloqueo estricto si el rol docente intenta consultar datos de delegados o directores
    if rol_norm == "docente" and ("vista_delegado" in q_lower or "todas las escuelas" in q_lower):
        denied = read_query(rol_norm, ambito_id, "SELECT * FROM vista_delegado")
        return {
            "reply": (
                f"El servidor MCP ha rechazado la consulta porque tu sesión actual ({rol_norm}) "
                "solo cuenta con permisos de lectura (GRANT SELECT) sobre los datos de tu aula "
                "(`vista_docente` y `vista_avisos_predictivos`)."
            ),
            "mcp_trace": {
                "db_role": f"role_{rol_norm}",
                "tools_called": ["list_tables", "read_query"],
                "sql_executed": "SELECT * FROM vista_delegado",
                "error": denied.get("error"),
            },
        }

    # Construcción de la consulta SQL real usando las vistas autorizadas del MCP
    if rol_norm == "docente":
        if any(w in q_lower for w in ["distancia", "desplazamiento", "traslado", "tiempo", "km", "3 km", "3km", "camino"]):
            sql = (
                "SELECT alumno_id, distancia_hogar_escuela_km, tiempo_desplazamiento, faltas_totales_calculadas, "
                "asistencia_pct_calculada, nota_trimestre_2_0_20, beneficiario_juntos "
                "FROM vista_docente WHERE distancia_hogar_escuela_km >= 3.0 "
                "ORDER BY faltas_totales_calculadas DESC LIMIT 10;"
            )
        elif any(w in q_lower for w in ["trabajo", "juntos", "beca", "subsidio", "economía", "horas"]):
            sql = (
                "SELECT alumno_id, beneficiario_juntos, horas_trabajo_semanal, prob_perdida_beca_pct, "
                "asistencia_pct_calculada, promedio_notas_calculado "
                "FROM vista_docente WHERE horas_trabajo_semanal > 0 OR beneficiario_juntos = 1 "
                "ORDER BY horas_trabajo_semanal DESC LIMIT 10;"
            )
        elif any(w in q_lower for w in ["nota", "rendimiento", "promedio", "calificación", "t3", "trimestre"]):
            sql = (
                "SELECT alumno_id, nota_trimestre_1_0_20, nota_trimestre_2_0_20, promedio_notas_calculado, "
                "prediccion_nota_t3, prob_repeticion_pct "
                "FROM vista_docente ORDER BY promedio_notas_calculado ASC LIMIT 10;"
            )
        else:
            sql = (
                "SELECT alumno_id, necesidad_intervencion, prob_abandono_pct, prediccion_nota_t3, "
                "factor_principal_riesgo, recomendacion_pedagogica "
                "FROM vista_avisos_predictivos LIMIT 10;"
            )

    elif rol_norm == "director":
        if any(w in q_lower for w in ["grado", "grupo", "sección", "comparativa", "aula"]):
            sql = (
                "SELECT escuela_id, grado_secundaria, total_estudiantes, asistencia_media_pct, "
                "promedio_notas, conectividad_hogar_pct, casos_prioridad_alta "
                "FROM vista_director ORDER BY grado_secundaria ASC;"
            )
        else:
            sql = (
                "SELECT escuela_id, grado_secundaria, total_estudiantes, asistencia_media_pct, "
                "promedio_notas, prob_abandono_media_pct, total_beneficiarios_juntos "
                "FROM vista_director ORDER BY casos_prioridad_alta DESC;"
            )

    else:  # DELEGADO / UGEL
        if any(w in q_lower for w in ["rural", "urbana", "zona", "brecha"]):
            sql = (
                "SELECT ugel, distrito, escuela_id, zona_escuela, total_estudiantes, "
                "asistencia_media_pct, promedio_notas, conectividad_hogar_pct "
                "FROM vista_delegado ORDER BY zona_escuela ASC, asistencia_media_pct ASC;"
            )
        else:
            sql = (
                "SELECT ugel, distrito, escuela_id, zona_escuela, total_estudiantes, "
                "asistencia_media_pct, promedio_notas, casos_prioridad_alta, prob_abandono_media_pct "
                "FROM vista_delegado ORDER BY casos_prioridad_alta DESC;"
            )

    res = read_query(rol_norm, ambito_id, sql)
    rows = res.get("rows", [])
    num_rows = len(rows)

    if num_rows == 0:
        reply_text = (
            f"He ejecutado la herramienta MCP `read_query` sobre `{primary_view}`, pero la base de datos "
            "actualmente no contiene registros que coincidan con la consulta (0 filas devueltas). "
            "La base de datos está inicializada y lista para recibir la importación de datos reales."
        )
    else:
        if rol_norm == "docente":
            codigos = ", ".join(r["alumno_id"] for r in rows[:4])
            reply_text = (
                f"Consultando la vista `{primary_view}` mediante el servidor MCP ({num_rows} registros encontrados, "
                f"ejemplos: {codigos}), se identifican factores relevantes de asistencia y contexto. "
                "La recomendación pedagógica es coordinar entrevistas formativas con las familias y flexibilizar "
                "los mecanismos de entrega para garantizar la permanencia escolar."
            )
        elif rol_norm == "director":
            reply_text = (
                f"A través de `{primary_view}` con MCP, se han consultado {num_rows} cohortes del centro educativo. "
                "Los datos consolidados permiten a la dirección priorizar recursos en aquellos grados con mayor "
                "índice de ausentismo o menor conectividad en hogar."
            )
        else:
            reply_text = (
                f"A nivel territorial mediante `{primary_view}`, se identifican {num_rows} escuelas en la red. "
                "La información orienta la asignación equitativa de subsidios de transporte escolar y conectividad."
            )

    # Si existe clave de Gemini, enriquecer la respuesta con el LLM
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and num_rows > 0:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = (
                "Eres el asistente pedagógico de DONPROFESOR (#Hack4Edu 2026). "
                "Responde en español profesional y cercano, SIN ningún emoticono ni emoji. "
                "Recuerda que la decisión final corresponde al criterio humano docente.\n\n"
                f"Rol: {rol_norm} | Ámbito: {ambito_id}\n"
                f"Pregunta: {question}\n"
                f"SQL ejecutado vía MCP: {sql}\n"
                f"Datos SQL: {json.dumps(rows[:8], ensure_ascii=False)}\n"
            )
            gem_resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            if gem_resp and gem_resp.text:
                reply_text = gem_resp.text.strip()
        except Exception:
            pass

    return {
        "reply": reply_text,
        "mcp_trace": {
            "db_role": f"role_{rol_norm}",
            "allowed_views": [t["table_or_view"] for t in mcp_tables],
            "tools_called": ["list_tables", "describe_table", "read_query"],
            "inspected_view": primary_view,
            "sql_executed": sql,
            "rows_returned": num_rows,
        },
    }
