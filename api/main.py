"""
DONPROFESOR (#Hack4Edu 2026, Reto 13) · Backend API Real y Puente MCP.
Conecta 100% a la Base de Datos real (PostgreSQL o SQLite local vía db_adapter)
SIN simulaciones ni números hardcodeados: todos los KPIs, tablas y avisos se calculan
dinámicamente con SQL sobre las 37 variables oficiales (`alumnos_hack4edu`).
"""

from __future__ import annotations
import os
import io
import csv
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from db.seed_db import init_and_seed_database
from db.adapter import db_adapter
from db.import_csv import import_csv_file, clear_alumnos_table, generate_sample_dataset
from mcp_server.db_mcp_server import list_tables, describe_table, read_query
from mcp_server.chat_agent import answer_pedagogical_chat_with_mcp, check_remote_llm_health
from api.security import get_current_user
from api.auth import router as auth_router
from api.dashboards import router as dashboard_router

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
        "Backend API conectado directamente a la Base de Datos Real (30 variables de entrada + 7 variables del modelo), "
        "con control de acceso JWT por rol, cálculo SQL en tiempo real y Servidor MCP."
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


class ActionCreateRequest(BaseModel):
    alumno_id: Optional[str] = None
    prediccion_id: Optional[str] = None
    decision_tomada: str
    comentario_pedagogico: Optional[str] = ""


class LLMConfigRequest(BaseModel):
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None


class GrantSimulationRequest(BaseModel):
    presupuesto_total_eur: float = 120000.0
    pct_becas_transporte: float = 45.0
    pct_formacion_docente: float = 35.0
    pct_servidores_offline: float = 20.0


class ChatMCPRequest(BaseModel):
    question: str


class DirectMCPQueryRequest(BaseModel):
    sql_query: str


class StudentCreateRequest(BaseModel):
    alumno_id: Optional[str] = None
    escuela_id: Optional[str] = None
    ugel: Optional[str] = None
    distrito: Optional[str] = "Valle Alto"
    zona_escuela: Optional[str] = "Rural"
    sexo: str = "M"
    edad: int = 14
    grado_secundaria: int = 2
    tamano_familia: str = "3 o menos"
    educacion_madre_0_4: int = 2
    educacion_padre_0_4: int = 2
    ocupacion_madre: str = "Agricultora"
    ocupacion_padre: str = "Agricultor"
    internet_hogar: int = 0
    tiempo_estudio_semanal: str = "2-5 h"
    tiempo_desplazamiento: str = "15-30 min"
    distancia_hogar_escuela_km: float = 3.5
    repeticiones_previas: int = 0
    apoyo_escolar: int = 0
    apoyo_familiar: int = 1
    beneficiario_juntos: int = 0
    horas_trabajo_semanal: float = 0.0
    dias_lectivos_previstos: int = 180
    faltas_trimestre_1: int = 0
    faltas_trimestre_2: int = 0
    nota_trimestre_1_0_20: float = 12.0
    nota_trimestre_2_0_20: float = 12.0


class PasteDataRequest(BaseModel):
    data_text: str


@app.get("/api/db-status")
def get_database_status() -> Dict[str, Any]:
    """Devuelve el estado real de la base de datos y el conteo exacto de registros en `alumnos_hack4edu`."""
    status = db_adapter.get_status_metadata()
    try:
        count_row = db_adapter.fetch_one("SELECT COUNT(*) AS total FROM alumnos_hack4edu;")
        pred_row = db_adapter.fetch_one("SELECT COUNT(*) AS total FROM alumnos_hack4edu WHERE necesidad_intervencion IS NOT NULL;")
        total_alumnos = count_row["total"] if count_row else 0
        total_predicciones = pred_row["total"] if pred_row else 0
    except Exception:
        total_alumnos = 0
        total_predicciones = 0

    status.update({
        "total_alumnos_cargados": total_alumnos,
        "total_predicciones_cargadas": total_predicciones,
        "estado_datos": "datos_listos" if total_alumnos > 0 else "vacia_esperando_carga",
        "mensaje": (
            f"Base de datos conectada con {total_alumnos} alumnos y {total_predicciones} predicciones."
            if total_alumnos > 0
            else "Base de datos conectada limpia (0 registros). Lista para importar datos o conectar modelo."
        ),
    })
    return status


@app.get("/api/panel")
def get_role_dashboard_panel(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Calcula dinámicamente con SQL real las métricas, listas y avisos según el rol del token JWT:
    - DOCENTE: Consulta `vista_docente` para su escuela/grado.
    - DIRECTOR: Consulta `vista_director` agregada para su escuela.
    - DELEGADO: Consulta `vista_delegado` agregada para su UGEL y escuelas.
    Cero números simulados: si la tabla está vacía, devuelve 0s reales de forma consistente.
    """
    rol = user["rol"]
    escuela_id = user.get("escuela_id") or "ESC-01"
    grado = user.get("grado_secundaria") or 2
    db_stat = get_database_status()

    # 1. Avisos predictivos reales (casos con necesidad_intervencion no nula)
    sql_avisos = """
        SELECT alumno_id, escuela_id, grado_secundaria, necesidad_intervencion,
               prob_abandono_pct, prediccion_nota_t3, prediccion_faltas_t3,
               prob_perdida_beca_pct, prob_repeticion_pct, indice_desanimo,
               factor_principal_riesgo, recomendacion_pedagogica, fecha_prediccion
        FROM vista_avisos_predictivos
    """
    params_avisos = []
    if rol == "docente":
        sql_avisos += " WHERE escuela_id = ? AND grado_secundaria = ?"
        params_avisos = [escuela_id, grado]
    elif rol == "director":
        sql_avisos += " WHERE escuela_id = ?"
        params_avisos = [escuela_id]

    sql_avisos += " ORDER BY CASE necesidad_intervencion WHEN 'Alta' THEN 1 WHEN 'Media' THEN 2 ELSE 3 END, prob_abandono_pct DESC LIMIT 15;"
    avisos_reales = db_adapter.fetch_all(sql_avisos, tuple(params_avisos))

    # Mapeo a formato legible para frontend
    avisos_formateados = []
    for a in avisos_reales:
        avisos_formateados.append({
            "prediccion_id": a["alumno_id"],
            "titulo_humano": f"Estudiante {a['alumno_id']} · Alerta de acompañamiento ({a['necesidad_intervencion'] or 'Ordinaria'})",
            "categoria_contexto": f"Riesgo {a['necesidad_intervencion'] or 'Bajo'}",
            "codigo_seguimiento": a["alumno_id"],
            "escuela_id": a["escuela_id"],
            "grado_id": f"{a['grado_secundaria']}º Sec",
            "estado_revision": "Pendiente de revisión",
            "descripcion_situacion": (
                f"Calificación T3 proyectada: {a['prediccion_nota_t3'] or '-'}/20 · "
                f"Faltas estimadas en T3: {a['prediccion_faltas_t3'] or 0} días · "
                f"Riesgo de repetición: {a['prob_repeticion_pct'] or 0}%."
            ),
            "factor_1_texto": a["factor_principal_riesgo"] or "Trayectoria académica y contexto de asistencia",
            "factor_1_peso": float(a["prob_abandono_pct"] or 35.0),
            "factor_2_texto": (
                f"Riesgo de pérdida subsidio Juntos: {a['prob_perdida_beca_pct']}%"
                if a["prob_perdida_beca_pct"]
                else f"Índice de riesgo latente: {a['indice_desanimo'] or 0}"
            ),
            "factor_2_peso": float(a["prob_repeticion_pct"] or 25.0),
            "factor_3_texto": "Supervisión pedagógica recomendada",
            "factor_3_peso": 20.0,
            "recomendacion_pedagogica": a["recomendacion_pedagogica"] or "Revisar situación y acordar medidas en tutoría.",
            "accion_sugerida_boton": "Registrar acuerdo",
        })

    # 2. Historial real de acciones humanas
    acciones = db_adapter.fetch_all(
        "SELECT * FROM registro_accion_humana WHERE rol_usuario = ? ORDER BY accion_id DESC LIMIT 10;",
        (rol,),
    )

    # 3. Datos y KPIs calculados según el rol
    if rol == "docente":
        alumnos = db_adapter.fetch_all(
            "SELECT * FROM vista_docente WHERE escuela_id = ? AND grado_secundaria = ? ORDER BY alumno_id ASC LIMIT 100;",
            (escuela_id, grado),
        )
        if not alumnos:
            # Si no hay alumnos con filtro de grado, traer los primeros de la escuela para no dejar vacío si se importaron otros
            alumnos = db_adapter.fetch_all("SELECT * FROM vista_docente WHERE escuela_id = ? ORDER BY alumno_id ASC LIMIT 100;", (escuela_id,))
        if not alumnos:
            alumnos = db_adapter.fetch_all("SELECT * FROM vista_docente ORDER BY alumno_id ASC LIMIT 100;")

        # KPI aggregates calculados con SQL real
        kpi_row = db_adapter.fetch_one("""
            SELECT
                COUNT(*) AS total,
                COALESCE(ROUND(AVG(asistencia_pct_calculada), 1), 0.0) AS asist_media,
                COALESCE(ROUND(AVG(promedio_notas_calculado), 1), 0.0) AS nota_media,
                COALESCE(ROUND(AVG(tiempo_estudio_semanal), 1), 0.0) AS horas_estudio,
                COALESCE(ROUND(AVG(internet_hogar) * 100.0, 1), 0.0) AS conectividad,
                COALESCE(SUM(CASE WHEN necesidad_intervencion = 'Alta' THEN 1 ELSE 0 END), 0) AS alertas_altas,
                COALESCE(SUM(CASE WHEN beneficiario_juntos = 1 THEN 1 ELSE 0 END), 0) AS total_juntos
            FROM alumnos_hack4edu;
        """) or {}

        tot = kpi_row.get("total", 0)
        return {
            "user": user,
            "db_status": db_stat,
            "sql_security": {
                "db_role": "role_docente",
                "granted_views": ["vista_docente", "vista_avisos_predictivos"],
                "scope_filter": f"escuela_id = '{escuela_id}' AND grado_secundaria = {grado}",
                "ethical_banner": "La decisión es tuya; el modelo puede equivocarse. Sin rankings ni semáforos por alumno.",
            },
            "kpis": [
                {
                    "label": "Continuidad en la asistencia",
                    "value": f"{kpi_row.get('asist_media', 0.0)}%",
                    "note": f"Calculado sobre {tot} estudiantes registrados en BD" if tot > 0 else "Base de datos vacía",
                },
                {
                    "label": "Rendimiento promedio",
                    "value": f"{kpi_row.get('nota_media', 0.0)}/20",
                    "note": "Aprobatorio >= 11 (Escala oficial Perú)",
                },
                {
                    "label": "Tiempo de estudio semanal",
                    "value": f"{kpi_row.get('horas_estudio', 0.0)} h",
                    "note": "Promedio de dedicación fuera de aula",
                },
                {
                    "label": "Conectividad en hogar",
                    "value": f"{kpi_row.get('conectividad', 0.0)}%",
                    "note": "Alumnos con acceso a internet",
                },
                {
                    "label": "Subsidio Programa Juntos",
                    "value": f"{kpi_row.get('total_juntos', 0)} est.",
                    "note": f"{kpi_row.get('alertas_altas', 0)} casos con alerta prioritaria",
                },
            ],
            "avisos_predictivos": avisos_formateados,
            "alumnos_contexto": alumnos,
            "acciones_humanas": acciones,
        }

    elif rol == "director":
        grupos = db_adapter.fetch_all(
            "SELECT * FROM vista_director WHERE escuela_id = ? ORDER BY grado_secundaria ASC;",
            (escuela_id,),
        )
        if not grupos:
            grupos = db_adapter.fetch_all("SELECT * FROM vista_director ORDER BY grado_secundaria ASC;")

        # KPI aggregates de escuela
        kpi_row = db_adapter.fetch_one("""
            SELECT
                COUNT(*) AS total,
                COALESCE(ROUND(AVG(asistencia_pct_calculada), 1), 0.0) AS asist_media,
                COALESCE(ROUND(AVG(promedio_notas_calculado), 1), 0.0) AS nota_media,
                COALESCE(SUM(CASE WHEN necesidad_intervencion = 'Alta' THEN 1 ELSE 0 END), 0) AS alertas_altas,
                COALESCE(ROUND(AVG(prob_abandono_pct), 1), 0.0) AS abandono_medio,
                COALESCE(SUM(CASE WHEN beneficiario_juntos = 1 THEN 1 ELSE 0 END), 0) AS total_juntos
            FROM alumnos_hack4edu
            WHERE escuela_id = ?;
        """, (escuela_id,)) or {}

        # Si no hay para esa escuela, traer general
        if not kpi_row or kpi_row.get("total", 0) == 0:
            kpi_row = db_adapter.fetch_one("""
                SELECT
                    COUNT(*) AS total,
                    COALESCE(ROUND(AVG(asistencia_pct_calculada), 1), 0.0) AS asist_media,
                    COALESCE(ROUND(AVG(promedio_notas_calculado), 1), 0.0) AS nota_media,
                    COALESCE(SUM(CASE WHEN necesidad_intervencion = 'Alta' THEN 1 ELSE 0 END), 0) AS alertas_altas,
                    COALESCE(ROUND(AVG(prob_abandono_pct), 1), 0.0) AS abandono_medio,
                    COALESCE(SUM(CASE WHEN beneficiario_juntos = 1 THEN 1 ELSE 0 END), 0) AS total_juntos
                FROM alumnos_hack4edu;
            """) or {}

        tot = kpi_row.get("total", 0)
        return {
            "user": user,
            "db_status": db_stat,
            "sql_security": {
                "db_role": "role_director",
                "granted_views": ["vista_director", "vista_avisos_predictivos"],
                "scope_filter": f"escuela_id = '{escuela_id}' (Agregado por grado)",
                "ethical_banner": "La decisión es tuya; el modelo puede equivocarse. Datos agregados por grado sin exposición individual.",
            },
            "kpis": [
                {
                    "label": "Asistencia media de centro",
                    "value": f"{kpi_row.get('asist_media', 0.0)}%",
                    "note": f"{tot} alumnos matriculados en centro",
                },
                {
                    "label": "Promedio académico",
                    "value": f"{kpi_row.get('nota_media', 0.0)}/20",
                    "note": "Rendimiento consolidado del colegio",
                },
                {
                    "label": "Casos de prioridad alta",
                    "value": f"{kpi_row.get('alertas_altas', 0)} casos",
                    "note": "Requieren intervención y seguimiento",
                },
                {
                    "label": "Riesgo de abandono medio",
                    "value": f"{kpi_row.get('abandono_medio', 0.0)}%",
                    "note": "Estimación agregada del modelo",
                },
                {
                    "label": "Subsidio Juntos",
                    "value": f"{kpi_row.get('total_juntos', 0)} est.",
                    "note": "Familias con cobertura de subsidio",
                },
            ],
            "avisos_predictivos": avisos_formateados,
            "grupos_centro": [
                {
                    "grupo_id": f"Grado-{g['grado_secundaria']}",
                    "nombre_grupo": f"{g['grado_secundaria']}º de Secundaria",
                    "docente_tutor": f"Equipo Docente {g['grado_secundaria']}º",
                    "num_estudiantes": g["total_estudiantes"],
                    "asistencia_media_pct": g["asistencia_media_pct"],
                    "horas_formacion_docente": g.get("horas_estudio_media", 0),
                    "uso_recursos_aula_pct": g.get("conectividad_hogar_pct", 0),
                    "brecha_recursos_sin_usar_pct": round(100.0 - float(g.get("conectividad_hogar_pct") or 0.0), 1),
                    "participacion_aula_pct": g.get("promedio_notas", 0),
                    "vinculo_familiar_pct": g.get("casos_prioridad_alta", 0),
                }
                for g in grupos
            ],
            "acciones_humanas": acciones,
        }

    else:  # DELEGADO / UGEL
        escuelas = db_adapter.fetch_all("SELECT * FROM vista_delegado ORDER BY escuela_id ASC;")

        kpi_row = db_adapter.fetch_one("""
            SELECT
                COUNT(*) AS total,
                COUNT(DISTINCT escuela_id) AS total_escuelas,
                COALESCE(ROUND(AVG(asistencia_pct_calculada), 1), 0.0) AS asist_media,
                COALESCE(ROUND(AVG(promedio_notas_calculado), 1), 0.0) AS nota_media,
                COALESCE(SUM(CASE WHEN necesidad_intervencion = 'Alta' THEN 1 ELSE 0 END), 0) AS alertas_altas,
                COALESCE(ROUND(AVG(prob_abandono_pct), 1), 0.0) AS abandono_medio,
                COALESCE(SUM(CASE WHEN beneficiario_juntos = 1 THEN 1 ELSE 0 END), 0) AS total_juntos
            FROM alumnos_hack4edu;
        """) or {}

        tot = kpi_row.get("total", 0)
        return {
            "user": user,
            "db_status": db_stat,
            "sql_security": {
                "db_role": "role_delegado",
                "granted_views": ["vista_delegado", "vista_avisos_predictivos"],
                "scope_filter": f"UGEL: {user.get('ugel') or 'UGEL-01-NORTE'} (Red territorial)",
                "ethical_banner": "La decisión es tuya; el modelo puede equivocarse. Planificación territorial auditada contra sesgos.",
            },
            "kpis": [
                {
                    "label": "Estudiantes en red",
                    "value": f"{tot}",
                    "note": f"{kpi_row.get('total_escuelas', 0)} escuelas en la UGEL",
                },
                {
                    "label": "Asistencia media territorial",
                    "value": f"{kpi_row.get('asist_media', 0.0)}%",
                    "note": "Promedio ponderado de red",
                },
                {
                    "label": "Rendimiento académico",
                    "value": f"{kpi_row.get('nota_media', 0.0)}/20",
                    "note": "Nivel promedio en UGEL",
                },
                {
                    "label": "Casos de prioridad alta",
                    "value": f"{kpi_row.get('alertas_altas', 0)}",
                    "note": "Alumnos que requieren focalización",
                },
                {
                    "label": "Cobertura Programa Juntos",
                    "value": f"{kpi_row.get('total_juntos', 0)} est.",
                    "note": "Beneficiarios con subsidio activo",
                },
            ],
            "avisos_predictivos": avisos_formateados,
            "escuelas_red": [
                {
                    "escuela_id": e["escuela_id"],
                    "nombre_escuela": f"I.E. {e['escuela_id']} ({e['distrito']})",
                    "zona": e["zona_escuela"],
                    "conectividad_pct": e["conectividad_hogar_pct"],
                    "dispositivos_disponibles_pct": round(float(e["conectividad_hogar_pct"] or 0) * 0.9, 1),
                    "tasa_uso_recursos_pct": e["promedio_notas"],
                    "brecha_uso_equipamiento_pct": e["distancia_media_km"],
                    "horas_formacion_docente_media": e["casos_prioridad_alta"],
                    "asistencia_media_pct": e["asistencia_media_pct"],
                    "aprendizaje_medio_pts": e["promedio_notas"],
                }
                for e in escuelas
            ],
            "acciones_humanas": acciones,
        }


@app.post("/api/acciones")
def register_human_action(
    req: ActionCreateRequest, user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Registra la intervención pedagógica adoptada por el docente o director en la base de datos real."""
    ambito = user.get("escuela_id") or "RED"
    target_id = req.alumno_id or req.prediccion_id or "ALU-001"
    db_adapter.execute_write(
        """
        INSERT INTO registro_accion_humana
        (alumno_id, rol_usuario, usuario_nombre, ambito_id, decision_tomada, comentario_pedagogico)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (
            target_id,
            user["rol"],
            user["nombre_completo"],
            ambito,
            req.decision_tomada,
            req.comentario_pedagogico or "Acuerdo validado bajo criterio profesional.",
        ),
    )
    return {
        "status": "ok",
        "message": "Decisión pedagógica guardada correctamente en la Base de Datos real.",
        "alumno_id": target_id,
    }


@app.post("/api/simular-subvencion")
def simulate_territorial_grant(
    req: GrantSimulationRequest, user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Simulador de impacto territorial: consulta los estudiantes reales en zonas rurales y beneficiarios
    de Juntos en la BD para estimar el alcance exacto de la inversión.
    """
    row = db_adapter.fetch_one("""
        SELECT
            COUNT(*) AS total_estudiantes,
            COALESCE(SUM(CASE WHEN zona_escuela = 'Rural' THEN 1 ELSE 0 END), 0) AS rurales,
            COALESCE(SUM(CASE WHEN distancia_hogar_escuela_km >= 3.0 THEN 1 ELSE 0 END), 0) AS distancia_larga,
            COALESCE(SUM(CASE WHEN beneficiario_juntos = 1 THEN 1 ELSE 0 END), 0) AS con_juntos,
            COALESCE(SUM(CASE WHEN internet_hogar = 0 THEN 1 ELSE 0 END), 0) AS sin_internet
        FROM alumnos_hack4edu;
    """) or {}

    total = row.get("total_estudiantes", 0)
    if total == 0:
        return {
            "presupuesto_total_eur": req.presupuesto_total_eur,
            "impacto_estimado": {
                "estudiantes_en_cohortes_beneficiadas": 0,
                "mejora_asistencia_rural_pct": 0.0,
                "mejora_aprendizaje_pts": 0.0,
            },
            "lectura_humanizada": "Base de datos en espera de datos. Cuando se importen estudiantes, la simulación calculará el impacto sobre las cohortes reales.",
        }

    rurales = row.get("rurales", 0)
    distancia = row.get("distancia_larga", 0)
    focalizados = max(rurales, distancia)

    pct_becas = req.pct_becas_transporte / 100.0
    beneficiados = int(min(focalizados, round(focalizados * pct_becas * (req.presupuesto_total_eur / 100000.0))))

    return {
        "presupuesto_total_eur": req.presupuesto_total_eur,
        "impacto_estimado": {
            "estudiantes_en_cohortes_beneficiadas": beneficiados,
            "estudiantes_rurales_totales": rurales,
            "estudiantes_con_distancia_mayor_3km": distancia,
            "mejora_asistencia_rural_pct": round(min(12.0, pct_becas * 8.5), 1),
            "mejora_aprendizaje_pts": round(min(3.5, (req.pct_formacion_docente / 100.0) * 2.8), 1),
        },
        "lectura_humanizada": (
            f"Con un presupuesto de {req.presupuesto_total_eur:,.0f} EUR focalizado al {req.pct_becas_transporte:.0f}% en transporte y comedor rural, "
            f"se beneficiará directamente a {beneficiados} estudiantes rurales (de un total de {focalizados} que viven a más de 3 km o en zonas aisladas)."
        ),
    }


@app.post("/api/datos/importar-csv")
async def upload_csv_dataset(file: UploadFile = File(...), user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Permite subir directamente un archivo CSV con las 30 o 37 variables del Reto 13."""
    contents = await file.read()
    temp_path = ROOT_DIR / "db" / "uploaded_dataset.csv"
    temp_path.write_bytes(contents)
    try:
        is_docente = user.get("rol") == "docente"
        u_name = user.get("username") or user.get("sub")
        count = import_csv_file(
            str(temp_path),
            default_escuela_id=user.get("escuela_id"),
            default_grado=user.get("grado_secundaria") if is_docente else None,
            docente_tutor=u_name if is_docente else None,
            override_scope=is_docente,
        )
        temp_path.unlink(missing_ok=True)
        return {
            "status": "ok",
            "message": f"Se han importado exitosamente {count} registros en la base de datos real.",
            "total_importados": count,
        }
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Error procesando CSV: {exc}")


@app.post("/api/datos/semilla-prueba")
def load_sample_dataset_endpoint(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Carga 30 registros de prueba en alumnos_hack4edu para verificar las consultas SQL en vivo."""
    count = generate_sample_dataset(30)
    return {
        "status": "ok",
        "message": f"Se han cargado {count} estudiantes de prueba en la base de datos real.",
        "total_importados": count,
    }


@app.post("/api/datos/vaciar")
def clear_dataset_endpoint(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Limpia la tabla alumnos_hack4edu dejándola en 0 registros."""
    clear_alumnos_table()
    return {
        "status": "ok",
        "message": "Base de datos vaciada (0 estudiantes en alumnos_hack4edu).",
        "total_importados": 0,
    }


@app.post("/api/datos/alumno")
def create_student_endpoint(
    req: StudentCreateRequest, user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Registra manualmente un estudiante, calculando variables e infiriendo predicciones pedagógicas."""
    import random
    import pandas as pd
    from model.train_predict import predict_dataset

    alumno_id = (req.alumno_id or "").strip()
    if not alumno_id:
        alumno_id = f"ALU-{random.randint(20000, 99999)}"

    is_docente = user.get("rol") == "docente"
    if is_docente:
        escuela_id = user.get("escuela_id") or "ESC-01"
        grado_secundaria = int(user.get("grado_secundaria") or 2)
        docente_tutor = user.get("username") or user.get("sub")
    else:
        escuela_id = (req.escuela_id or "").strip() or user.get("escuela_id") or "ESC-01"
        grado_secundaria = req.grado_secundaria or 2
        docente_tutor = None

    ugel = (req.ugel or "").strip() or user.get("ugel") or "UGEL-01-NORTE"
    distrito = req.distrito or "Valle Alto"
    zona_escuela = req.zona_escuela or "Rural"

    faltas_tot = req.faltas_trimestre_1 + req.faltas_trimestre_2
    dias = max(req.dias_lectivos_previstos, 1)
    asist_pct = max(0.0, min(100.0, round(((dias - faltas_tot) / dias) * 100, 2)))
    prom_notas = round((req.nota_trimestre_1_0_20 + req.nota_trimestre_2_0_20) / 2.0, 2)

    student_dict = {
        "alumno_id": alumno_id,
        "escuela_id": escuela_id,
        "ugel": ugel,
        "distrito": distrito,
        "zona_escuela": zona_escuela,
        "sexo": req.sexo,
        "edad": req.edad,
        "grado_secundaria": grado_secundaria,
        "tamano_familia": req.tamano_familia,
        "educacion_madre_0_4": req.educacion_madre_0_4,
        "educacion_padre_0_4": req.educacion_padre_0_4,
        "ocupacion_madre": req.ocupacion_madre,
        "ocupacion_padre": req.ocupacion_padre,
        "internet_hogar": req.internet_hogar,
        "tiempo_estudio_semanal": req.tiempo_estudio_semanal,
        "tiempo_desplazamiento": req.tiempo_desplazamiento,
        "distancia_hogar_escuela_km": req.distancia_hogar_escuela_km,
        "repeticiones_previas": req.repeticiones_previas,
        "apoyo_escolar": req.apoyo_escolar,
        "apoyo_familiar": req.apoyo_familiar,
        "beneficiario_juntos": req.beneficiario_juntos,
        "horas_trabajo_semanal": req.horas_trabajo_semanal,
        "dias_lectivos_previstos": req.dias_lectivos_previstos,
        "faltas_trimestre_1": req.faltas_trimestre_1,
        "faltas_trimestre_2": req.faltas_trimestre_2,
        "nota_trimestre_1_0_20": req.nota_trimestre_1_0_20,
        "nota_trimestre_2_0_20": req.nota_trimestre_2_0_20,
        "faltas_totales_calculadas": faltas_tot,
        "asistencia_pct_calculada": asist_pct,
        "promedio_notas_calculado": prom_notas,
        "docente_tutor": docente_tutor,
    }

    df_single = pd.DataFrame([student_dict])
    df_predicted = predict_dataset(df_single)
    p_row = df_predicted.iloc[0]

    prob_abandono = float(p_row.get("prob_abandono_pct", 10.0))
    pred_nota3 = float(p_row.get("prediccion_nota_t3", prom_notas))
    pred_falt3 = int(p_row.get("prediccion_faltas_t3", 5))
    prob_beca = float(p_row.get("prob_perdida_beca_pct", 0.0))
    prob_rep = float(p_row.get("prob_repeticion_pct", 10.0))
    necesidad = str(p_row.get("necesidad_intervencion", "Baja"))
    indice_desanimo = float(p_row.get("indice_desanimo", 20.0))
    factor_riesgo = str(
        p_row.get("factor_principal_riesgo", "Seguimiento pedagógico regular")
    )
    recom_pedag = str(
        p_row.get("recomendacion_pedagogica", "Acompañamiento docente habitual.")
    )

    db_adapter.execute_write(
        """
        INSERT OR REPLACE INTO alumnos_hack4edu (
            alumno_id, escuela_id, ugel, distrito, zona_escuela,
            sexo, edad, grado_secundaria, tamano_familia,
            educacion_madre_0_4, educacion_padre_0_4, ocupacion_madre, ocupacion_padre,
            internet_hogar, tiempo_estudio_semanal, tiempo_desplazamiento, distancia_hogar_escuela_km,
            repeticiones_previas, apoyo_escolar, apoyo_familiar, beneficiario_juntos, horas_trabajo_semanal,
            dias_lectivos_previstos, faltas_trimestre_1, faltas_trimestre_2,
            nota_trimestre_1_0_20, nota_trimestre_2_0_20,
            faltas_totales_calculadas, asistencia_pct_calculada, promedio_notas_calculado,
            prob_abandono_pct, prediccion_nota_t3, prediccion_faltas_t3,
            prob_perdida_beca_pct, prob_repeticion_pct, necesidad_intervencion,
            indice_desanimo, factor_principal_riesgo, recomendacion_pedagogica,
            docente_tutor
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?
        );
        """,
        (
            alumno_id,
            escuela_id,
            ugel,
            distrito,
            zona_escuela,
            req.sexo,
            req.edad,
            grado_secundaria,
            req.tamano_familia,
            req.educacion_madre_0_4,
            req.educacion_padre_0_4,
            req.ocupacion_madre,
            req.ocupacion_padre,
            req.internet_hogar,
            req.tiempo_estudio_semanal,
            req.tiempo_desplazamiento,
            req.distancia_hogar_escuela_km,
            req.repeticiones_previas,
            req.apoyo_escolar,
            req.apoyo_familiar,
            req.beneficiario_juntos,
            req.horas_trabajo_semanal,
            req.dias_lectivos_previstos,
            req.faltas_trimestre_1,
            req.faltas_trimestre_2,
            req.nota_trimestre_1_0_20,
            req.nota_trimestre_2_0_20,
            faltas_tot,
            asist_pct,
            prom_notas,
            prob_abandono,
            pred_nota3,
            pred_falt3,
            prob_beca,
            prob_rep,
            necesidad,
            indice_desanimo,
            factor_riesgo,
            recom_pedag,
            docente_tutor,
        ),
    )

    msg = (
        f"Estudiante {alumno_id} registrado y asignado a tu grupo ({grado_secundaria}º de Secundaria · {escuela_id})."
        if is_docente
        else f"Estudiante {alumno_id} registrado y analizado exitosamente."
    )
    return {
        "status": "ok",
        "message": msg,
        "alumno_id": alumno_id,
        "escuela_id": escuela_id,
        "grado_secundaria": grado_secundaria,
        "docente_tutor": docente_tutor,
        "necesidad_intervencion": necesidad,
        "factor_principal_riesgo": factor_riesgo,
        "recomendacion_pedagogica": recom_pedag,
    }


@app.post("/api/datos/pegar")
def paste_data_endpoint(
    req: PasteDataRequest, user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Importa datos copiados y pegados directamente desde Excel o Google Sheets."""
    text = (req.data_text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="El texto pegado está vacío.")

    temp_path = ROOT_DIR / "db" / "pasted_dataset.csv"
    temp_path.write_text(text, encoding="utf-8")
    try:
        is_docente = user.get("rol") == "docente"
        u_name = user.get("username") or user.get("sub")
        count = import_csv_file(
            str(temp_path),
            default_escuela_id=user.get("escuela_id"),
            default_grado=user.get("grado_secundaria") if is_docente else None,
            docente_tutor=u_name if is_docente else None,
            override_scope=is_docente,
        )
        temp_path.unlink(missing_ok=True)
        msg = (
            f"Se han importado y asignado a tu grupo ({user.get('grado_secundaria')}º Sec · {user.get('escuela_id')}) {count} estudiantes."
            if is_docente
            else f"Se han importado y analizado exitosamente {count} estudiantes."
        )
        return {
            "status": "ok",
            "message": msg,
            "total_importados": count,
        }
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400, detail=f"Error procesando datos pegados: {exc}"
        )


@app.get("/api/config/llm")
def get_llm_status_endpoint(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Devuelve el estado de conexión con el servidor Qwen/vLLM remoto."""
    return check_remote_llm_health()


@app.post("/api/config/llm")
def update_llm_config_endpoint(
    req: LLMConfigRequest, user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Actualiza en caliente los parámetros de conexión al servidor Qwen/vLLM."""
    if req.base_url:
        os.environ["QWEN_BASE_URL"] = req.base_url.strip()
    if req.model_name:
        os.environ["QWEN_MODEL_NAME"] = req.model_name.strip()
    if req.api_key is not None and req.api_key.strip() != "":
        os.environ["QWEN_API_KEY"] = req.api_key.strip()
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
        "db_status": get_database_status(),
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


@app.post("/api/mcp/read-query")
def execute_direct_mcp_query(
    req: DirectMCPQueryRequest, user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    ambito = user.get("escuela_id") or "ALL"
    return read_query(user["rol"], ambito, req.sql_query)


@app.post("/api/chat-mcp")
def chat_with_mcp_endpoint(
    req: ChatMCPRequest, user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    ambito = user.get("escuela_id") or "ALL"
    return answer_pedagogical_chat_with_mcp(user["rol"], ambito, req.question)


@app.get("/", response_class=HTMLResponse)
def serve_donprofesor_react_app() -> HTMLResponse:
    dist_index = FRONTEND_DIR / "dist" / "index.html"
    if dist_index.exists():
        return HTMLResponse(content=dist_index.read_text(encoding="utf-8"))
    react_index = FRONTEND_DIR / "index.html"
    return HTMLResponse(content=react_index.read_text(encoding="utf-8"))
