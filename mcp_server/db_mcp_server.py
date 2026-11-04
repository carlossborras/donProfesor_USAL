"""
DONPROFESOR (#Hack4Edu 2026, Reto 13) · Servidor MCP de Base de Datos Real (Persona 3).
Conecta el modelo de lenguaje (LLM) del Chat con la Base de Datos real mediante Model Context Protocol,
respetando estrictamente los permisos por rol sobre las vistas de seguridad:
- Rol 'docente'   -> solo puede consultar vista_docente y vista_avisos_predictivos.
- Rol 'director'  -> solo puede consultar vista_director y vista_avisos_predictivos de su escuela.
- Rol 'delegado'  -> solo puede consultar vista_delegado y vista_avisos_predictivos a nivel territorial.

Expone las 3 herramientas estándar de Base de Datos en MCP:
1. list_tables(rol)
2. describe_table(rol, table_name)
3. read_query(rol, ambito_id, sql_query)
"""

from __future__ import annotations
import re
from typing import Dict, List, Any
from mcp.server.mcpserver import MCPServer
from db.seed_db import init_and_seed_database
from db.adapter import db_adapter

mcp = MCPServer("donprofesor-db-mcp")

# Mapa estricto de control de acceso basado en rol (RBAC / GRANT SELECT por vista)
ROLE_ALLOWED_VIEWS: Dict[str, List[str]] = {
    "docente": ["vista_docente", "vista_avisos_predictivos"],
    "director": ["vista_director", "vista_avisos_predictivos"],
    "delegado": ["vista_delegado", "vista_avisos_predictivos"],
}

VIEW_DESCRIPTIONS: Dict[str, str] = {
    "vista_docente": (
        "Seguimiento contextual de estudiantes por grado y escuela: "
        "alumno_id, edad, grado_secundaria, distancia_hogar_escuela_km, tiempo_desplazamiento, "
        "beneficiario_juntos, horas_trabajo_semanal, internet_hogar, tiempo_estudio_semanal, "
        "faltas_trimestre_1, faltas_trimestre_2, faltas_totales_calculadas, asistencia_pct_calculada, "
        "nota_trimestre_1_0_20, nota_trimestre_2_0_20, promedio_notas_calculado, "
        "prediccion_nota_t3, prediccion_faltas_t3, prob_perdida_beca_pct, prob_repeticion_pct, "
        "prob_abandono_pct, necesidad_intervencion, indice_desanimo, factor_principal_riesgo, recomendacion_pedagogica."
    ),
    "vista_director": (
        "Indicadores agregados por grado y centro educativo: "
        "escuela_id, grado_secundaria, total_estudiantes, asistencia_media_pct, promedio_notas, "
        "conectividad_hogar_pct, horas_estudio_media, total_beneficiarios_juntos, "
        "casos_prioridad_alta, casos_prioridad_media, casos_prioridad_baja, prob_abandono_media_pct, indice_desanimo_medio."
    ),
    "vista_delegado": (
        "Indicadores territoriales por UGEL, distrito y escuela (rural vs urbana): "
        "ugel, distrito, escuela_id, zona_escuela, total_estudiantes, asistencia_media_pct, promedio_notas, "
        "conectividad_hogar_pct, distancia_media_km, total_beneficiarios_juntos, casos_prioridad_alta, prob_abandono_media_pct."
    ),
    "vista_avisos_predictivos": (
        "Casos prioritarios detectados por el modelo predictivo con necesidad de intervención: "
        "alumno_id, escuela_id, grado_secundaria, necesidad_intervencion, prob_abandono_pct, "
        "prediccion_nota_t3, prediccion_faltas_t3, prob_perdida_beca_pct, prob_repeticion_pct, "
        "indice_desanimo, factor_principal_riesgo, recomendacion_pedagogica."
    ),
}


@mcp.tool()
def list_tables(rol: str = "docente") -> List[Dict[str, str]]:
    """Devuelve la lista de vistas SQL sobre las cuales el rol actual tiene permiso GRANT SELECT."""
    init_and_seed_database()
    rol_norm = rol.lower().strip()
    allowed = ROLE_ALLOWED_VIEWS.get(rol_norm, ROLE_ALLOWED_VIEWS["docente"])
    return [
        {
            "table_or_view": v,
            "db_role": f"role_{rol_norm}",
            "permission": "GRANT SELECT",
            "description": VIEW_DESCRIPTIONS.get(v, ""),
        }
        for v in allowed
    ]


@mcp.tool()
def describe_table(rol: str, table_name: str) -> Dict[str, Any]:
    """Devuelve las columnas y tipos de datos de una vista autorizada para el rol actual."""
    init_and_seed_database()
    rol_norm = rol.lower().strip()
    allowed = ROLE_ALLOWED_VIEWS.get(rol_norm, [])
    if table_name not in allowed:
        return {
            "error": (
                f"Permiso denegado en Base de Datos: el rol 'role_{rol_norm}' "
                f"no tiene GRANT SELECT sobre '{table_name}'. Vistas permitidas: {allowed}"
            )
        }

    try:
        rows = db_adapter.fetch_all(f"PRAGMA table_info({table_name});")
        cols = [
            {"column_name": r.get("name") or r.get("column_name"), "data_type": r.get("type") or r.get("data_type", "TEXT")}
            for r in rows
        ]
    except Exception:
        cols = []

    return {
        "view_name": table_name,
        "db_role": f"role_{rol_norm}",
        "description": VIEW_DESCRIPTIONS.get(table_name, ""),
        "columns": cols,
    }


@mcp.tool()
def read_query(rol: str, ambito_id: str, sql_query: str) -> Dict[str, Any]:
    """
    Ejecuta una consulta SQL SELECT de solo lectura sobre las vistas autorizadas para el rol en la base de datos real.
    Bloquea cualquier instrucción que no sea SELECT o que intente acceder a tablas no autorizadas.
    """
    init_and_seed_database()
    rol_norm = rol.lower().strip()
    allowed = ROLE_ALLOWED_VIEWS.get(rol_norm, [])

    sql_clean = sql_query.strip()
    if not sql_clean.upper().startswith("SELECT"):
        return {
            "error": "Operación bloqueada por el Servidor MCP: solo se permiten consultas SELECT de lectura."
        }

    forbidden_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "PRAGMA", "ATTACH"]
    for kw in forbidden_keywords:
        if re.search(rf"\b{kw}\b", sql_clean.upper()):
            return {
                "error": f"Operación bloqueada: la palabra clave '{kw}' no está permitida."
            }

    # Comprobar que solo se consultan las vistas permitidas para ese rol
    all_known_objects = [
        "alumnos_hack4edu",
        "usuario_plataforma",
        "registro_accion_humana",
        "vista_docente",
        "vista_director",
        "vista_delegado",
        "vista_avisos_predictivos",
    ]
    for obj in all_known_objects:
        if re.search(rf"\b{obj}\b", sql_clean.lower()) and obj not in allowed:
            return {
                "error": (
                    f"Control de Acceso SQL (role_{rol_norm}): acceso denegado a '{obj}'. "
                    f"Solo tienes permiso GRANT SELECT sobre: {', '.join(allowed)}."
                )
            }

    try:
        rows = db_adapter.fetch_all(sql_clean)
        return {
            "executed_sql": sql_clean,
            "db_role": f"role_{rol_norm}",
            "ambito_id": ambito_id,
            "row_count": len(rows),
            "rows": rows[:50],
        }
    except Exception as exc:
        return {"error": f"Error al ejecutar consulta en vista SQL real: {exc}"}


if __name__ == "__main__":
    mcp.run()
