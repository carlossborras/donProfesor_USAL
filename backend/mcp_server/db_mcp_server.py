"""
DONPROFESOR (#Hack4Edu 2026, Reto 13) · Servidor MCP de Base de Datos Real (Persona 3).
Conecta el modelo de lenguaje (LLM) del Chat con la Base de Datos real mediante Model Context Protocol,
respetando estrictamente los permisos por rol sobre las vistas de seguridad:
- Rol 'docente'   -> solo vista_docente, filtrada a SU grupo (escuela + grado).
- Rol 'director'  -> solo vista_director (agregada, k >= 5), filtrada a SU escuela.
- Rol 'delegado'  -> solo vista_delegado (agregada, k >= 5), filtrada a SU UGEL.

El filtro de ámbito se aplica en la propia base de datos: antes de ejecutar la consulta se crean vistas
TEMPORALES con el mismo nombre y el filtro del usuario, de modo que aunque el modelo de lenguaje escriba
cualquier SELECT, solo puede leer filas de su ámbito.

Expone las 3 herramientas estándar de Base de Datos en MCP:
1. list_tables(rol)
2. describe_table(rol, table_name)
3. read_query(rol, ambito_id, sql_query)
"""

from __future__ import annotations
import re
from typing import Dict, List, Any
from mcp.server.mcpserver import MCPServer
from db.seed_db import init_and_seed_database, ensure_database, get_sqlite_connection
from db.adapter import db_adapter

mcp = MCPServer("donprofesor-db-mcp")

# Mapa estricto de control de acceso basado en rol (RBAC / GRANT SELECT por vista)
ROLE_ALLOWED_VIEWS: Dict[str, List[str]] = {
    "docente": ["vista_docente"],
    "director": ["vista_director"],
    "delegado": ["vista_delegado"],
}

# Columna de cada vista sobre la que se aplica el ámbito
_FILTRO_VISTA = {
    "vista_docente": ("docente", "UPPER(TRIM(escuela_id)) = UPPER(TRIM({escuela})) AND grado_secundaria = {grado}"),
    "vista_director": ("director", "UPPER(TRIM(escuela_id)) = UPPER(TRIM({escuela}))"),
    "vista_delegado": ("delegado", "UPPER(TRIM(ugel)) = UPPER(TRIM({ugel}))"),
}


def _literal(valor: Any) -> str:
    """Literal SQL seguro para SQLite (solo se usa con datos del token, nunca con texto del usuario)."""
    if valor is None:
        return "NULL"
    if isinstance(valor, (int, float)):
        return str(int(valor)) if float(valor).is_integer() else str(float(valor))
    return "'" + str(valor).replace("'", "''") + "'"


def describe_scope(scope: Any) -> str:
    if isinstance(scope, dict):
        partes = [f"{k}={scope.get(k)}" for k in ("escuela_id", "grado_secundaria", "ugel") if scope.get(k)]
        return ", ".join(partes) or "sin ámbito"
    return str(scope)

VIEW_DESCRIPTIONS: Dict[str, str] = {
    "vista_docente": (
        "Seguimiento contextual de estudiantes por grado y escuela: "
        "alumno_id, edad, grado_secundaria, distancia_hogar_escuela_km, tiempo_desplazamiento, "
        "beneficiario_juntos, horas_trabajo_semanal, internet_hogar, tiempo_estudio_semanal, "
        "faltas_trimestre_1, faltas_trimestre_2, faltas_totales_calculadas, asistencia_pct_calculada, "
        "nota_trimestre_1_0_20, nota_trimestre_2_0_20, promedio_notas_calculado, "
        "prediccion_nota_t1, prediccion_nota_t2, prediccion_nota_t3, prediccion_faltas_t1, prediccion_faltas_t2, "
        "prediccion_faltas_t3, necesidad_intervencion, indice_desanimo (0-10), factor_principal_riesgo, recomendacion_pedagogica. "
        "Sin probabilidades individuales."
    ),
    "vista_director": (
        "Indicadores agregados por grado y centro educativo: "
        "escuela_id, grado_secundaria, total_estudiantes, asistencia_media_pct, promedio_notas, "
        "conectividad_hogar_pct, nota_t3_prevista_media, total_beneficiarios_juntos, "
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
def read_query(rol: str, ambito_id: Any, sql_query: str) -> Dict[str, Any]:
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

    # Tolerancia a sinónimos comunes de columnas en las consultas de lenguaje natural
    synonyms = {
        r"\bdistancia_al_centro\b": "distancia_hogar_escuela_km",
        r"\bdistancia_km\b": "distancia_hogar_escuela_km",
        r"\bdistancia\b": "distancia_hogar_escuela_km",
        r"\btiempo_traslado\b": "tiempo_desplazamiento",
        r"\bhoras_trabajo\b": "horas_trabajo_semanal",
        r"\btrabajo_semanal\b": "horas_trabajo_semanal",
        r"\bfaltas\b": "faltas_totales_calculadas",
        r"\basistencia\b": "asistencia_pct_calculada",
        r"\bpromedio\b": "promedio_notas_calculado",
        r"\bnota_media\b": "promedio_notas_calculado",
    }
    for pat, rep in synonyms.items():
        sql_clean = re.sub(pat, rep, sql_clean, flags=re.IGNORECASE)

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

    if re.search(r"\b(main|temp|sqlite_\w+)\b", sql_clean.lower()):
        return {"error": "Operación bloqueada: no se permiten referencias a esquemas internos de la base de datos."}
    if not isinstance(ambito_id, dict):
        return {"error": "Falta el ámbito de la sesión: no se puede ejecutar la consulta."}
    if db_adapter.mode != "PROVISIONAL_SQLITE_SEED":
        return {"error": "Las consultas del asistente solo están disponibles con la base de datos local."}

    ensure_database()
    conn = get_sqlite_connection()
    try:
        for vista in allowed:
            rol_vista, plantilla = _FILTRO_VISTA[vista]
            if rol_vista != rol_norm:
                continue
            filtro = plantilla.format(
                escuela=_literal(ambito_id.get("escuela_id")),
                grado=_literal(int(ambito_id.get("grado_secundaria") or 0)),
                ugel=_literal(ambito_id.get("ugel")),
            )
            conn.execute(f"CREATE TEMP VIEW {vista} AS SELECT * FROM main.{vista} WHERE {filtro};")
        cursor = conn.execute(sql_clean)
        rows = [dict(r) for r in cursor.fetchmany(50)]
        return {
            "executed_sql": sql_clean,
            "db_role": f"role_{rol_norm}",
            "ambito_id": describe_scope(ambito_id),
            "row_count": len(rows),
            "rows": rows,
        }
    except Exception as exc:
        return {"error": f"Error al ejecutar la consulta: {exc}"}
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run()
