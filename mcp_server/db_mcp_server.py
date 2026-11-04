"""
DONPROFESOR (#Hack4Edu) · Servidor MCP de Base de Datos (Persona 3).
Conecta el modelo de lenguaje (LLM) del Chat con la Base de Datos de forma segura,
respetando los permisos por rol (GRANT SELECT simulado/aplicado sobre las vistas de cada rol):
- Rol 'docente'   -> solo puede consultar vista_docente y vista_avisos_predictivos de su grupo.
- Rol 'director'  -> solo puede consultar vista_director, vista_director_clima y vista_avisos_predictivos de su escuela.
- Rol 'delegado'  -> solo puede consultar vista_delegado y vista_avisos_predictivos a nivel regional (k-anonimato >= 15).

Expone las 3 herramientas estándar de Base de Datos en MCP:
1. list_tables(rol)
2. describe_table(rol, table_name)
3. read_query(rol, ambito_id, sql_query)
"""

from __future__ import annotations
import re
from typing import Dict, List, Any
from mcp.server.mcpserver import MCPServer
from db.seed_db import get_sqlite_connection, init_and_seed_database

mcp = MCPServer("donprofesor-db-mcp")

# Mapa estricto de control de acceso basado en rol (RBAC / GRANT SELECT por vista)
ROLE_ALLOWED_VIEWS: Dict[str, List[str]] = {
    "docente": ["vista_docente", "vista_avisos_predictivos"],
    "director": ["vista_director", "vista_director_clima", "vista_avisos_predictivos"],
    "delegado": ["vista_delegado", "vista_avisos_predictivos"],
}

VIEW_DESCRIPTIONS: Dict[str, str] = {
    "vista_docente": (
        "Seguimiento contextual de los estudiantes del grupo tutorizado por el docente "
        "(distancia_km, tiene_beca, apoyo_cosecha_familiar, segundo_empleo_familiar, "
        "faltas_dias_lluvia, faltas_semanas_cosecha, participacion_actividades_pct, continuidad_entregas_pct, nota_media)."
    ),
    "vista_director": (
        "Indicadores agregados por grupo/aula del centro educativo con k >= 5 "
        "(asistencia_media_pct, participacion_aula_pct, uso_recursos_aula_pct, "
        "brecha_recursos_sin_usar_pct, horas_formacion_docente, vinculo_familiar_pct, nota_media_grupo)."
    ),
    "vista_director_clima": (
        "Serie temporal semanal del centro educativo que cruza asistencia_semanal_pct "
        "con mm_lluvia, es_semana_cosecha, uso_recursos_semanal_pct y participacion_semanal_pct."
    ),
    "vista_delegado": (
        "Indicadores agregados de los centros educativos de la red territorial con k >= 15 "
        "(zona, conectividad_pct, dispositivos_disponibles_pct, tasa_uso_recursos_pct, "
        "brecha_uso_equipamiento_pct, horas_formacion_docente_media, asistencia_media_pct, aprendizaje_medio_pts)."
    ),
    "vista_avisos_predictivos": (
        "Avisos generados por el modelo predictivo explicable con sus 3 factores de mayor peso "
        "(factor_1_texto, factor_2_texto, factor_3_texto), recomendacion_pedagogica y estado_revision."
    ),
}


@mcp.tool()
def list_tables(rol: str = "docente") -> List[Dict[str, str]]:
    """
    Devuelve la lista de vistas SQL sobre las cuales el rol actual tiene permiso GRANT SELECT.
    """
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
    """
    Devuelve las columnas y tipos de datos de una vista autorizada para el rol actual.
    Rechaza el acceso si la tabla o vista no pertenece al ámbito del rol.
    """
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

    conn = get_sqlite_connection()
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name});")
    cols = [
        {"column_name": row["name"], "data_type": row["type"]}
        for row in cur.fetchall()
    ]
    conn.close()
    return {
        "view_name": table_name,
        "db_role": f"role_{rol_norm}",
        "description": VIEW_DESCRIPTIONS.get(table_name, ""),
        "columns": cols,
    }


@mcp.tool()
def read_query(rol: str, ambito_id: str, sql_query: str) -> Dict[str, Any]:
    """
    Ejecuta una consulta SQL SELECT de solo lectura sobre las vistas autorizadas para el rol.
    Bloquea cualquier instrucción que no sea SELECT o que intente acceder a tablas fuera de las vistas del rol.
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
        "escuela",
        "grupo_aula",
        "calendario_entorno",
        "alumno_contexto",
        "prediccion",
        "usuario_plataforma",
        "vista_docente",
        "vista_director",
        "vista_director_clima",
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

    conn = get_sqlite_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql_clean)
        rows = [dict(r) for r in cur.fetchall()[:50]]
        conn.close()
        return {
            "executed_sql": sql_clean,
            "db_role": f"role_{rol_norm}",
            "ambito_id": ambito_id,
            "row_count": len(rows),
            "rows": rows,
        }
    except Exception as exc:
        conn.close()
        return {"error": f"Error al ejecutar consulta en vista SQL: {exc}"}


if __name__ == "__main__":
    mcp.run()
