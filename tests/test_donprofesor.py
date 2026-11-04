"""
Pruebas automatizadas de integración para DONPROFESOR (#Hack4Edu 2026, Reto 13).
Verifica:
1. Base de datos real vacía por defecto (0 registros simulados) y estado de conexión limpio.
2. Autenticación JWT y cálculo dinámico de KPIs por rol mediante SQL real.
3. Importación dinámica y cálculo de agregados cuando se cargan registros.
4. Servidor MCP con control estricto de vistas por rol.
"""

from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from api.main import app
from db.adapter import db_adapter
from db.import_csv import clear_alumnos_table, generate_sample_dataset
from mcp_server.db_mcp_server import list_tables, describe_table, read_query

client = TestClient(app)
ROOT_DIR = Path(__file__).resolve().parent.parent


def test_empty_database_and_login():
    # 1. Asegurar que la base de datos está limpia y vacía (0 alumnos)
    clear_alumnos_table()

    status_resp = client.get("/api/db-status")
    assert status_resp.status_code == 200
    st = status_resp.json()
    assert st["total_alumnos_cargados"] == 0
    assert st["estado_datos"] == "vacia_esperando_carga"

    # 2. Login con los tres roles sobre la BD real
    for role in ["docente", "director", "delegado"]:
        resp = client.post(
            "/api/auth/login",
            json={"username": role, "password": "donprofesor2026"},
        )
        assert resp.status_code == 200
        data = resp.json()
        token = data["access_token"]
        assert data["user"]["rol"] == role

        panel_resp = client.get(
            "/api/panel", headers={"Authorization": f"Bearer {token}"}
        )
        assert panel_resp.status_code == 200
        pdata = panel_resp.json()
        assert pdata["user"]["rol"] == role
        assert len(pdata["kpis"]) == 5
        # En base de datos limpia, los KPIs no crashean y reflejan 0
        assert pdata["kpis"][0]["value"] in ["0.0%", "0"]


def test_dynamic_sql_calculations_with_imported_data():
    # 1. Cargar datos de prueba realistas para verificar que los cálculos SQL son 100% reales
    count = generate_sample_dataset(30)
    assert count == 30

    login = client.post(
        "/api/auth/login",
        json={"username": "director", "password": "donprofesor2026"},
    ).json()
    token = login["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    panel_resp = client.get("/api/panel", headers=headers)
    assert panel_resp.status_code == 200
    pdata = panel_resp.json()
    assert len(pdata["grupos_centro"]) > 0
    # Comprobar que los cálculos se actualizan con los datos reales
    assert pdata["db_status"]["total_alumnos_cargados"] == 30

    # 2. Registrar acción humana pedagógica sobre un alumno real
    act_resp = client.post(
        "/api/acciones",
        headers=headers,
        json={
            "alumno_id": "ALU-0001",
            "decision_tomada": "Coordinación con tutor y seguimiento familiar semanal",
            "comentario_pedagogico": "Validado en reunión de acompañamiento.",
        },
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["status"] == "ok"

    # 3. Limpiar de nuevo la tabla para dejar la base de datos limpia lista para el equipo
    clear_alumnos_table()
    assert client.get("/api/db-status").json()["total_alumnos_cargados"] == 0


def test_mcp_role_based_sql_restrictions():
    # 1. El rol docente solo tiene acceso a vista_docente y vista_avisos_predictivos
    docente_tables = [t["table_or_view"] for t in list_tables("docente")]
    assert "vista_docente" in docente_tables
    assert "vista_delegado" not in docente_tables

    # 2. Intento de consultar vista_delegado desde el rol docente debe ser bloqueado por el MCP
    blocked = read_query("docente", "ESC-01", "SELECT * FROM vista_delegado")
    assert "error" in blocked
    assert "acceso denegado" in blocked["error"].lower()

    # 3. Consulta legítima sobre vista_docente funciona correctamente
    allowed = read_query(
        "docente",
        "ESC-01",
        "SELECT alumno_id, distancia_hogar_escuela_km FROM vista_docente WHERE distancia_hogar_escuela_km >= 3.0",
    )
    assert "rows" in allowed
    assert "executed_sql" in allowed


def test_modular_react_frontend_served_and_web_app_imports():
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    assert "root" in root_resp.text

    # Verificar que importar web/app.py funciona limpiamente sin errores
    cmd = [
        sys.executable,
        "-c",
        "import runpy; m = runpy.run_path('web/app.py', run_name='not_main'); assert 'app' in m",
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Error importando web/app.py: {proc.stderr}"


def test_langgraph_react_agent_and_ethical_guardrails():
    from mcp_server.chat_agent import (
        answer_pedagogical_chat_with_mcp,
        create_langgraph_react_agent_for_session,
    )

    # 1. Verificar construcción del grafo ReAct de LangGraph y sus 3 tools MCP
    graph, tools = create_langgraph_react_agent_for_session(
        rol="docente",
        ambito_id="ESC-001",
        base_url="http://127.0.0.1:11434/v1",
        model_name="qwen2.5-coder",
    )
    assert graph is not None
    assert len(tools) == 3
    tool_names = [t.name for t in tools]
    assert "list_authorized_views" in tool_names
    assert "describe_view" in tool_names
    assert "execute_sql_query" in tool_names

    # 2. Barrera ética: Bloqueo de peticiones punitivas automatizadas
    blocked = answer_pedagogical_chat_with_mcp(
        "docente", "ESC-001", "Quiero expulsar y suspender automáticamente a los peores alumnos"
    )
    assert "no realiza clasificaciones punitivas" in blocked["reply"].lower()
    assert blocked["mcp_trace"]["tools_called"] == ["ethical_guardrail_block"]

    # 3. Flujo normal con base de datos real
    res = answer_pedagogical_chat_with_mcp(
        "docente", "ESC-001", "¿Qué alumnos tienen problemas de distancia o transporte?"
    )
    assert "reply" in res
    assert "mcp_trace" in res
    assert "execute_sql_query" in res["mcp_trace"]["tools_called"]


def test_student_manual_entry_and_paste_batch():
    clear_alumnos_table()

    # Login como docente
    login = client.post(
        "/api/auth/login",
        json={"username": "docente", "password": "donprofesor2026"},
    ).json()
    token = login["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Probar registro manual vía POST /api/datos/alumno
    student_payload = {
        "alumno_id": "ALU-TEST-999",
        "escuela_id": "ESC-01",
        "grado_secundaria": 2,
        "sexo": "F",
        "edad": 14,
        "zona_escuela": "Rural",
        "distancia_hogar_escuela_km": 4.5,
        "tiempo_desplazamiento": "30-60 min",
        "tiempo_estudio_semanal": "2-5 h",
        "tamano_familia": "Mas de 3",
        "internet_hogar": 0,
        "horas_trabajo_semanal": 5,
        "beneficiario_juntos": 1,
        "apoyo_familiar": 1,
        "apoyo_escolar": 0,
        "faltas_trimestre_1": 6,
        "faltas_trimestre_2": 14,
        "nota_trimestre_1_0_20": 13.0,
        "nota_trimestre_2_0_20": 9.5,
    }
    resp = client.post("/api/datos/alumno", headers=headers, json=student_payload)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["status"] == "ok"
    assert res_data["alumno_id"] == "ALU-TEST-999"
    assert "necesidad_intervencion" in res_data
    assert "recomendacion_pedagogica" in res_data

    # Comprobar que la base de datos ahora tiene 1 registro con todas las columnas
    st = client.get("/api/db-status").json()
    assert st["total_alumnos_cargados"] == 1

    # 2. Probar importación pegada vía POST /api/datos/pegar (formato Excel / TSV)
    tsv_content = (
        "alumno_id\tsexo\tedad\tgrado_secundaria\tdistancia_hogar_escuela_km\tfaltas_trimestre_1\tfaltas_trimestre_2\tnota_trimestre_1_0_20\tnota_trimestre_2_0_20\n"
        "ALU-PASTE-01\tM\t15\t3\t2.1\t1\t3\t15.0\t14.5\n"
        "ALU-PASTE-02\tF\t14\t2\t5.8\t8\t18\t11.0\t8.0\n"
    )
    paste_resp = client.post(
        "/api/datos/pegar",
        headers=headers,
        json={"data_text": tsv_content},
    )
    assert paste_resp.status_code == 200
    paste_data = paste_resp.json()
    assert paste_data["status"] == "ok"
    assert paste_data["total_importados"] == 2

    # La base de datos ahora tiene 3 estudiantes
    st2 = client.get("/api/db-status").json()
    assert st2["total_alumnos_cargados"] == 3

    # Limpiar tabla
    clear_alumnos_table()


def test_teacher_group_assignment_and_scope_isolation():
    clear_alumnos_table()

    # 1. Login como docente de ESC-01, Grado 2
    login_a = client.post(
        "/api/auth/login",
        json={"username": "docente", "password": "donprofesor2026"},
    ).json()
    token_a = login_a["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Docente añade alumno intentando pasar otro grado por payload
    resp_a = client.post(
        "/api/datos/alumno",
        headers=headers_a,
        json={
            "alumno_id": "ALU-GRUPO-A",
            "escuela_id": "ESC-99",
            "grado_secundaria": 5,
            "sexo": "F",
            "edad": 14,
            "distancia_hogar_escuela_km": 3.0,
            "faltas_trimestre_1": 2,
            "faltas_trimestre_2": 4,
            "nota_trimestre_1_0_20": 14.0,
            "nota_trimestre_2_0_20": 13.0,
        },
    )
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    # Verifica que el backend forzó el grupo del docente
    assert data_a["escuela_id"] == "ESC-01"
    assert data_a["grado_secundaria"] == 2
    assert data_a["docente_tutor"] == "docente"

    # 2. Registrar otro docente (ESC-02, Grado 4)
    import secrets
    u_b = f"docente_{secrets.token_hex(4)}"
    reg_b = client.post(
        "/api/auth/register",
        json={
            "username": u_b,
            "password": "Password123",
            "nombre_completo": "Prof. Juan Pérez",
            "rol": "docente",
            "escuela_id": "ESC-02",
            "grado_secundaria": 4,
        },
    )
    assert reg_b.status_code == 201
    token_b = reg_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Docente B pega datos desde Excel sin especificar escuela ni grado
    tsv_b = (
        "alumno_id\tsexo\tedad\tdistancia_hogar_escuela_km\tfaltas_trimestre_1\tfaltas_trimestre_2\tnota_trimestre_1_0_20\tnota_trimestre_2_0_20\n"
        "ALU-GRUPO-B1\tM\t16\t2.0\t1\t1\t15.0\t16.0\n"
        "ALU-GRUPO-B2\tF\t16\t4.5\t5\t8\t11.0\t10.0\n"
    )
    resp_b = client.post("/api/datos/pegar", headers=headers_b, json={"data_text": tsv_b})
    assert resp_b.status_code == 200

    # Comprobar en base de datos que se asignaron a ESC-02, Grado 4 y docente_tutor = u_b
    b_rows = db_adapter.fetch_all("SELECT alumno_id, escuela_id, grado_secundaria, docente_tutor FROM alumnos_hack4edu WHERE alumno_id LIKE 'ALU-GRUPO-B%'")
    assert len(b_rows) == 2
    for r in b_rows:
        assert r["escuela_id"] == "ESC-02"
        assert r["grado_secundaria"] == 4
        assert r["docente_tutor"] == u_b

    # 3. Comprobar aislamiento en los paneles:
    # El docente A solo ve a ALU-GRUPO-A
    panel_a = client.get("/api/dashboard", headers=headers_a).json()
    assert panel_a["kpis"][0]["value"] == 1
    assert [a["alumno_id"] for a in panel_a["tablas"]["alumnos"]] == ["ALU-GRUPO-A"]

    # El docente B solo ve a sus 2 alumnos
    panel_b = client.get("/api/dashboard", headers=headers_b).json()
    assert panel_b["kpis"][0]["value"] == 2
    assert sorted([a["alumno_id"] for a in panel_b["tablas"]["alumnos"]]) == ["ALU-GRUPO-B1", "ALU-GRUPO-B2"]

    clear_alumnos_table()



