"""
Pruebas automatizadas de integración para Persona 3 (Base de Datos con Adaptador Provisional/PostgreSQL,
API JWT, Vistas SQL y Servidor MCP) y Persona 4 (Aplicación React Modular DONPROFESOR con los 3 Paneles).
"""

from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from api.main import app
from mcp_server.db_mcp_server import list_tables, describe_table, read_query

client = TestClient(app)
ROOT_DIR = Path(__file__).resolve().parent.parent


def test_login_and_role_views_access():
    for role in ["docente", "director", "delegado"]:
        resp = client.post(
            "/api/auth/login",
            json={"username": role, "password": "donprofesor2026"},
        )
        assert resp.status_code == 200
        data = resp.json()
        token = data["access_token"]
        assert data["user"]["rol"] == role
        assert "db_status" in data
        assert data["db_status"]["is_provisional"] is True

        panel_resp = client.get(
            "/api/panel", headers={"Authorization": f"Bearer {token}"}
        )
        assert panel_resp.status_code == 200
        panel_data = panel_resp.json()
        assert panel_data["user"]["rol"] == role
        assert panel_data["db_status"]["db_mode"] == "PROVISIONAL_SQLITE_SEED"
        assert len(panel_data["kpis"]) == 5
        assert len(panel_data["avisos_predictivos"]) >= 3


def test_mcp_role_based_sql_restrictions():
    # 1. El rol docente solo tiene acceso a vista_docente y vista_avisos_predictivos
    docente_tables = [t["table_or_view"] for t in list_tables("docente")]
    assert "vista_docente" in docente_tables
    assert "vista_delegado" not in docente_tables

    # 2. Intento de consultar vista_delegado desde el rol docente debe ser bloqueado por el MCP
    blocked = read_query("docente", "ESC-01-2B", "SELECT * FROM vista_delegado")
    assert "error" in blocked
    assert "acceso denegado" in blocked["error"].lower()

    # 3. Consulta legítima sobre vista_docente funciona correctamente
    allowed = read_query(
        "docente",
        "ESC-01-2B",
        "SELECT codigo_seguimiento, distancia_km FROM vista_docente WHERE distancia_km > 3.0",
    )
    assert "rows" in allowed
    assert allowed["row_count"] >= 4


def test_chat_mcp_and_human_action_registration():
    login = client.post(
        "/api/auth/login",
        json={"username": "director", "password": "donprofesor2026"},
    ).json()
    token = login["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Consultar al Chat conectado por MCP
    chat_resp = client.post(
        "/api/chat-mcp",
        headers=headers,
        json={"question": "¿En qué grupos se usan menos los recursos digitales y cuántas horas de formación tienen?"},
    )
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert "vista_director" in chat_data["mcp_trace"]["sql_executed"]
    assert chat_data["mcp_trace"]["rows_returned"] >= 4

    # Registrar acción humana sobre un aviso del modelo predictivo
    act_resp = client.post(
        "/api/acciones",
        headers=headers,
        json={
            "prediccion_id": "PRED-DIR-01",
            "decision_tomada": "Programar mentoría docente entre pares 3ºA y 1ºA",
            "comentario_pedagogico": "Acordado en reunión de dirección.",
        },
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["nuevo_estado"] == "Acuerdo registrado"


def test_modular_react_frontend_served_and_web_app_imports():
    # 1. Verificar que la raíz sirve el entry point de React y que los componentes modulares existen
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    assert "root" in root_resp.text

    for component_path in [
        "/src/App.jsx",
        "/src/components/EthicalBanner.jsx",
        "/src/components/Navbar.jsx",
        "/src/components/PredictiveAlertsPanel.jsx",
        "/src/components/RainHarvestChart.jsx",
        "/src/components/RoleViews.jsx",
        "/src/components/McpChatSidebar.jsx",
        "/src/components/Modals.jsx",
        "/src/styles/app.css",
    ]:
        comp_resp = client.get(component_path)
        assert comp_resp.status_code == 200, f"Fallo al servir {component_path}"

    # 2. Verificar que importar web/app.py desde el directorio raíz funciona sin ModuleNotFoundError
    cmd = [
        sys.executable,
        "-c",
        "import runpy; m = runpy.run_path('web/app.py', run_name='not_main'); assert 'app' in m",
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Error importando web/app.py: {proc.stderr}"
