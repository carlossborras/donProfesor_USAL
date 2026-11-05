"""
Pruebas de registro, inicio de sesión, control de acceso por rol y paneles con gráficos.

Usan una base de datos SQLite TEMPORAL (no tocan db/donprofesor.db ni rellenan la BD real):
los alumnos que se insertan aquí existen solo durante la prueba.
"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

import db.seed_db as seed_db

PASSWORD = "Prueba2026x"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(seed_db, "SQLITE_PATH", tmp_path / "test_donprofesor.db")
    monkeypatch.delenv("DONPROFESOR_CODIGO_REGISTRO_DIRECTOR", raising=False)
    from api.main import app

    with TestClient(app) as c:
        yield c


def _registrar(client, **extra):
    datos = {
        "username": "ana.docente",
        "password": PASSWORD,
        "nombre_completo": "Ana Quispe",
        "rol": "docente",
        "escuela_id": "esc-01",
        "grado_secundaria": 2,
    }
    datos.update(extra)
    return client.post("/api/auth/register", json=datos)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _insertar_alumnos(filas):
    """Inserta alumnos sintéticos SOLO en la BD temporal de la prueba."""
    conn = sqlite3.connect(str(seed_db.SQLITE_PATH))
    columnas = (
        "alumno_id, escuela_id, ugel, distrito, zona_escuela, sexo, edad, grado_secundaria, tamano_familia, "
        "educacion_madre_0_4, educacion_padre_0_4, ocupacion_madre, ocupacion_padre, internet_hogar, "
        "tiempo_estudio_semanal, tiempo_desplazamiento, distancia_hogar_escuela_km, repeticiones_previas, "
        "apoyo_escolar, apoyo_familiar, beneficiario_juntos, horas_trabajo_semanal, dias_lectivos_previstos, "
        "faltas_trimestre_1, faltas_trimestre_2, nota_trimestre_1_0_20, nota_trimestre_2_0_20, "
        "faltas_totales_calculadas, asistencia_pct_calculada, promedio_notas_calculado, prob_abandono_pct, "
        "prediccion_nota_t3, necesidad_intervencion, factor_principal_riesgo, recomendacion_pedagogica"
    )
    for i, (escuela, grado, ugel, zona, revision) in enumerate(filas):
        conn.execute(
            f"INSERT INTO alumnos_hack4edu ({columnas}) VALUES ({', '.join(['?'] * 35)})",
            (
                f"T-{i:03d}", escuela, ugel, "Distrito", zona, "F", 13, grado, 4,
                2, 2, "Agricultura", "Agricultura", i % 2, 6.0, 30, 2.0 + (i % 5), 0,
                1, 1, i % 2, 0.0 if i % 3 else 10.0, 180,
                3, 6, 12.0, 11.0, 9, 95.0, 11.5, 72.5,
                9.5, "Alta" if revision else "Baja", "Faltas en semanas de cosecha", "Tutoría con la familia",
            ),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Registro y login
# ---------------------------------------------------------------------------

def test_registro_devuelve_sesion_y_guarda_hash(client):
    r = _registrar(client)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["access_token"]
    assert cuerpo["user"]["rol"] == "docente"
    assert cuerpo["user"]["escuela_id"] == "ESC-01"
    assert "password_hash" not in cuerpo["user"]

    conn = sqlite3.connect(str(seed_db.SQLITE_PATH))
    guardado = conn.execute(
        "SELECT password_hash FROM usuario_plataforma WHERE username = 'ana.docente'"
    ).fetchone()[0]
    conn.close()
    assert guardado.startswith("pbkdf2_sha256$") and PASSWORD not in guardado


def test_registro_duplicado_409(client):
    assert _registrar(client).status_code == 201
    assert _registrar(client).status_code == 409


@pytest.mark.parametrize(
    "extra",
    [
        {"password": "corta1"},
        {"password": "sinnumeros"},
        {"username": "Ana Docente!"},
        {"rol": "docente", "grado_secundaria": None},
        {"rol": "director", "escuela_id": None},
        {"rol": "delegado", "ugel": None, "escuela_id": None},
        {"rol": "admin"},
    ],
)
def test_registro_valida_datos_422(client, extra):
    assert _registrar(client, **extra).status_code == 422


def test_codigo_de_invitacion(client, monkeypatch):
    monkeypatch.setenv("DONPROFESOR_CODIGO_REGISTRO_DIRECTOR", "clave-direccion")
    base = {"username": "dir.uno", "rol": "director", "grado_secundaria": None}
    assert _registrar(client, **base).status_code == 403
    assert _registrar(client, **base, codigo_invitacion="otra").status_code == 403
    assert _registrar(client, **base, codigo_invitacion="clave-direccion").status_code == 201


def test_login_correcto_e_incorrecto(client):
    _registrar(client)
    ok = client.post("/api/auth/login", json={"username": "ANA.DOCENTE", "password": PASSWORD})
    assert ok.status_code == 200 and ok.json()["user"]["username"] == "ana.docente"
    mal = client.post("/api/auth/login", json={"username": "ana.docente", "password": "otra123456"})
    assert mal.status_code == 401
    nadie = client.post("/api/auth/login", json={"username": "nadie", "password": "x"})
    assert nadie.status_code == 401
    assert mal.json()["detail"] == nadie.json()["detail"]  # no revela si el usuario existe


def test_usuario_antiguo_en_texto_plano_se_recifra(client):
    conn = sqlite3.connect(str(seed_db.SQLITE_PATH))
    conn.execute(
        "INSERT INTO usuario_plataforma VALUES ('viejo', 'clave2025', 'Usuario Antiguo', 'director', 'ESC-09', NULL, NULL, 'Dirección')"
    )
    conn.commit()
    conn.close()
    assert client.post("/api/auth/login", json={"username": "viejo", "password": "clave2025"}).status_code == 200
    conn = sqlite3.connect(str(seed_db.SQLITE_PATH))
    nuevo = conn.execute("SELECT password_hash FROM usuario_plataforma WHERE username='viejo'").fetchone()[0]
    conn.close()
    assert nuevo.startswith("pbkdf2_sha256$")


def test_me_y_tokens_invalidos(client):
    token = _registrar(client).json()["access_token"]
    assert client.get("/api/auth/me", headers=_auth(token)).json()["user"]["username"] == "ana.docente"
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=_auth("no.es.un.jwt")).status_code == 401


def test_demo_users_siguen_funcionando(client):
    for rol in ("docente", "director", "delegado"):
        r = client.post("/api/auth/login", json={"username": rol, "password": "donprofesor2026"})
        assert r.status_code == 200 and r.json()["user"]["rol"] == rol


# ---------------------------------------------------------------------------
# Paneles por rol
# ---------------------------------------------------------------------------

def test_cada_rol_solo_su_panel(client):
    tokens = {
        "docente": _registrar(client).json()["access_token"],
        "director": _registrar(client, username="dir.uno", rol="director", grado_secundaria=None).json()["access_token"],
        "delegado": _registrar(
            client, username="del.uno", rol="delegado", ugel="ugel-sur", escuela_id=None, grado_secundaria=None
        ).json()["access_token"],
    }
    for rol_usuario, token in tokens.items():
        assert client.get("/api/dashboard", headers=_auth(token)).json()["rol"] == rol_usuario
        for rol_panel in tokens:
            r = client.get(f"/api/dashboard/{rol_panel}", headers=_auth(token))
            assert r.status_code == (200 if rol_usuario == rol_panel else 403)
    assert client.get("/api/dashboard").status_code == 401


def test_paneles_vacios_sin_datos(client):
    token = _registrar(client).json()["access_token"]
    panel = client.get("/api/dashboard", headers=_auth(token)).json()
    assert panel["hay_datos"] is False
    assert panel["kpis"][0]["value"] == 0


def test_panel_docente_sin_probabilidades_ni_ranking(client):
    _insertar_alumnos([("ESC-01", 2, "UGEL-SUR", "Rural", i % 2 == 0) for i in range(6)])
    token = _registrar(client).json()["access_token"]
    panel = client.get("/api/dashboard", headers=_auth(token)).json()
    assert panel["hay_datos"] is True
    texto = str(panel).lower()
    for prohibido in ("prob_", "necesidad", "prediccion", "riesgo alto", "72.5"):
        assert prohibido not in texto, prohibido
    ids = [a["alumno_id"] for a in panel["tablas"]["alumnos"]]
    assert ids == sorted(ids)
    assert sum(a["sugerir_revision"] for a in panel["tablas"]["alumnos"]) == 3
    assert {"notas_por_trimestre", "distribucion_asistencia", "asistencia_vs_distancia"} <= set(panel["charts"])


def test_docente_solo_ve_su_grado(client):
    _insertar_alumnos([
        ("ESC-01", 2, "UGEL-SUR", "Rural", False), ("ESC-01", 3, "UGEL-SUR", "Rural", False),
        ("ESC-02", 2, "UGEL-SUR", "Rural", False),
    ])
    token = _registrar(client).json()["access_token"]
    panel = client.get("/api/dashboard", headers=_auth(token)).json()
    assert [a["alumno_id"] for a in panel["tablas"]["alumnos"]] == ["T-000"]


def test_director_oculta_grados_con_menos_de_5(client):
    _insertar_alumnos([("ESC-01", 1, "UGEL-SUR", "Rural", False)] * 5 + [("ESC-01", 2, "UGEL-SUR", "Rural", True)] * 3)
    token = _registrar(client, username="dir.uno", rol="director", grado_secundaria=None).json()["access_token"]
    panel = client.get("/api/dashboard", headers=_auth(token)).json()
    assert [g["grado"] for g in panel["tablas"]["grados"]] == [1]
    assert [g["grado"] for g in panel["tablas"]["grados_ocultos"]] == [2]
    assert all(g["n"] >= 5 for g in panel["tablas"]["grados"])


def test_delegado_solo_su_ugel_y_k_anonimato(client):
    _insertar_alumnos(
        [("ESC-01", 1, "UGEL-SUR", "Rural", False)] * 5
        + [("ESC-02", 1, "UGEL-SUR", "Urbana", False)] * 2
        + [("ESC-09", 1, "UGEL-NORTE", "Urbana", False)] * 6
    )
    token = _registrar(
        client, username="del.uno", rol="delegado", ugel="ugel-sur", escuela_id=None, grado_secundaria=None
    ).json()["access_token"]
    panel = client.get("/api/dashboard", headers=_auth(token)).json()
    assert [e["escuela_id"] for e in panel["tablas"]["escuelas"]] == ["ESC-01"]
    assert [e["escuela_id"] for e in panel["tablas"]["escuelas_ocultas"]] == ["ESC-02"]
    assert "ESC-09" not in str(panel)
