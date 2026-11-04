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
