"""
Pruebas de integración generales de DONPROFESOR (#Hack4Edu 2026, Reto 13):
  1. Base de datos vacía por defecto y paneles sin datos inventados.
  2. Servidor MCP: cada rol solo ve su vista y siempre filtrada por su ámbito.
  3. Frontend servido y web/app.py importable.
  4. Agente LangGraph y barrera ética.

Usan una base de datos SQLite TEMPORAL. Las pruebas del flujo de predicción están en test_predicciones.py.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import db.seed_db as seed_db
from mcp_server.db_mcp_server import list_tables, read_query

ROOT_DIR = Path(__file__).resolve().parent.parent
PASSWORD = "Prueba2026x"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(seed_db, "SQLITE_PATH", tmp_path / "test_general.db")
    monkeypatch.delenv("DONPROFESOR_CODIGO_REGISTRO_DOCENTE", raising=False)
    from api.main import app

    with TestClient(app) as c:
        yield c


def _token(client, username="ana.docente", **extra):
    datos = {"username": username, "password": PASSWORD, "nombre_completo": "Ana Quispe", "rol": "docente",
             "escuela_id": "ESC-01", "grado_secundaria": 2, **extra}
    r = client.post("/api/auth/register", json=datos)
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _insertar(alumno_id, escuela, grado, ugel="UGEL SUR"):
    conn = sqlite3.connect(str(seed_db.SQLITE_PATH))
    conn.execute(
        "INSERT INTO alumnos_hack4edu (alumno_id, escuela_id, grado_secundaria, ugel, distancia_hogar_escuela_km) "
        "VALUES (?, ?, ?, ?, ?)",
        (alumno_id, escuela, grado, ugel, 4.0),
    )
    conn.commit()
    conn.close()


def test_base_vacia_y_paneles_sin_datos_inventados(client):
    h = _token(client)
    estado = client.get("/api/db-status", headers=h).json()
    assert estado["total_alumnos_cargados"] == 0
    assert estado["estado_datos"] == "vacia_esperando_carga"
    panel = client.get("/api/panel", headers=h).json()
    assert panel["avisos_predictivos"] == []
    assert panel["user"]["rol"] == "docente"
    assert client.get("/api/db-status").status_code == 401


def test_mcp_solo_vista_del_rol_y_filtrada_por_ambito(client):
    _token(client)  # crea la base de datos temporal
    _insertar("A-1", "ESC-01", 2)
    _insertar("A-2", "ESC-01", 3)
    _insertar("A-3", "ESC-02", 2)

    vistas = [t["table_or_view"] for t in list_tables("docente")]
    assert vistas == ["vista_docente"]

    ambito = {"escuela_id": "esc-01", "grado_secundaria": 2, "ugel": None}
    bloqueada = read_query("docente", ambito, "SELECT * FROM vista_delegado")
    assert "acceso denegado" in bloqueada["error"].lower()
    assert "error" in read_query("docente", ambito, "SELECT * FROM alumnos_hack4edu")
    assert "error" in read_query("docente", ambito, "SELECT * FROM main.vista_docente")
    assert "error" in read_query("docente", ambito, "DELETE FROM vista_docente")
    assert "error" in read_query("docente", "ESC-01", "SELECT * FROM vista_docente")

    ok = read_query("docente", ambito, "SELECT alumno_id FROM vista_docente")
    assert [r["alumno_id"] for r in ok["rows"]] == ["A-1"]


def test_frontend_servido_y_web_app_importable(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "root" in r.text
    cmd = [sys.executable, "-c", "import runpy; m = runpy.run_path('web/app.py', run_name='not_main'); assert 'app' in m"]
    proc = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr


def test_agente_langgraph_y_barrera_etica(client, monkeypatch):
    monkeypatch.delenv("QWEN_BASE_URL", raising=False)
    from mcp_server.chat_agent import answer_pedagogical_chat_with_mcp, create_langgraph_react_agent_for_session

    ambito = {"escuela_id": "ESC-01", "grado_secundaria": 2, "ugel": None}
    graph, tools = create_langgraph_react_agent_for_session(
        rol="docente", ambito_id=ambito, base_url="http://127.0.0.1:9/v1", model_name="donprofesor-llm"
    )
    assert graph is not None
    assert {t.name for t in tools} == {"list_authorized_views", "describe_view", "execute_sql_query"}

    bloqueada = answer_pedagogical_chat_with_mcp("docente", ambito, "Quiero expulsar automáticamente a los peores alumnos")
    assert "no realiza clasificaciones punitivas" in bloqueada["reply"].lower()

    respuesta = answer_pedagogical_chat_with_mcp("docente", ambito, "¿Qué alumnos viven lejos?")
    assert "reply" in respuesta and "mcp_trace" in respuesta
