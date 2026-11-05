"""
Pruebas del flujo de predicción: alta / importación de estudiantes -> predicción con el modelo ->
pestañas «Predicciones», «Para revisar» y «Cómo vamos», siempre dentro del ámbito del token.

No necesitan el modelo real ni scikit-learn: se inyecta un modelo FALSO con la misma interfaz
(predict / predict_proba / classes_) que los Pipelines de entrenadorModelo.py. Usan una base de
datos SQLite temporal (no tocan db/donprofesor.db).
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from fastapi.testclient import TestClient

import db.seed_db as seed_db
from model import predictor

PASSWORD = "Prueba2026x"
NUM = ["distancia_hogar_escuela_km", "horas_trabajo_semanal", "dias_lectivos_previstos"]
CAT = ["sexo", "zona_escuela", "ocupacion_madre", "ocupacion_padre", "tiempo_estudio_semanal",
       "tiempo_desplazamiento", "tamano_familia"]
BIN = ["educacion_madre_0_4", "educacion_padre_0_4", "grado_secundaria", "edad", "repeticiones_previas",
       "internet_hogar", "apoyo_escolar", "apoyo_familiar", "beneficiario_juntos"]


def _riesgo(X):
    """Riesgo sintético: crece con la distancia y las horas de trabajo (0..1)."""
    d = X["distancia_hogar_escuela_km"].astype(float).fillna(2.0).to_numpy()
    h = X["horas_trabajo_semanal"].astype(float).fillna(0.0).to_numpy()
    return np.clip(0.05 + d / 20.0 + h / 40.0, 0.0, 0.95)


class FakeBinario:
    classes_ = np.array([0, 1])

    def predict_proba(self, X):
        r = _riesgo(X)
        return np.column_stack([1 - r, r])

    def predict(self, X):
        return (_riesgo(X) >= 0.5).astype(int)


class FakeNecesidad:
    classes_ = np.array(["Alta", "Baja", "Media"])

    def predict_proba(self, X):
        r = _riesgo(X)
        alta = np.where(r >= 0.5, 0.7, 0.1)
        media = np.where((r >= 0.25) & (r < 0.5), 0.6, 0.2)
        return np.column_stack([alta, 1 - alta - media, media])

    def predict(self, X):
        p = self.predict_proba(X)
        return self.classes_[p.argmax(axis=1)]


class FakeRegresor:
    def __init__(self, base, pendiente):
        self.base, self.pendiente = base, pendiente

    def predict(self, X):
        return self.base + self.pendiente * _riesgo(X)


def _bundle():
    modelos = {
        "abandono_escolar": FakeBinario(),
        "perdida_beca": FakeBinario(),
        "repeticion": FakeBinario(),
        "necesidad_intervencion": FakeNecesidad(),
        "nota_trimestre_1_0_20": FakeRegresor(15, -8),
        "nota_trimestre_2_0_20": FakeRegresor(15, -9),
        "nota_trimestre_3_real": FakeRegresor(15, -10),
        "faltas_trimestre_1": FakeRegresor(2, 10),
        "faltas_trimestre_2": FakeRegresor(2, 12),
        "ausencias_trimestre_3": FakeRegresor(2, 14),
        "desanimo_calculado": FakeRegresor(3, 8),
    }
    categorias = {
        "sexo": ["F", "M"], "zona_escuela": ["Rural", "Urbana"],
        "ocupacion_madre": ["Agricultura", "Comercio", "Hogar"], "ocupacion_padre": ["Agricultura", "Comercio", "Hogar"],
        "tiempo_estudio_semanal": ["Menos de 2 h", "2-5 h", "5-10 h", "Mas de 10 h"],
        "tiempo_desplazamiento": ["Menos de 15 min", "15-30 min", "30-60 min", "Mas de 60 min"],
        "tamano_familia": ["3 o menos", "Mas de 3"],
    }
    referencia = {"distancia_hogar_escuela_km": 2.0, "horas_trabajo_semanal": 0.0, "dias_lectivos_previstos": 180,
                  **{c: v[0] for c, v in categorias.items()}, **{b: 0 for b in BIN}}
    return predictor.ModelBundle(modelos=modelos, numericas=NUM, categoricas=CAT, binarias=BIN,
                                 categorias=categorias, referencia=referencia, version="modelo-falso-pruebas")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(seed_db, "SQLITE_PATH", tmp_path / "test_predicciones.db")
    for rol in ("DOCENTE", "DIRECTOR", "DELEGADO"):
        monkeypatch.delenv(f"DONPROFESOR_CODIGO_REGISTRO_{rol}", raising=False)
    predictor.set_bundle_for_tests(_bundle())
    from api.main import app

    with TestClient(app) as c:
        yield c
    predictor.set_bundle_for_tests(None)


def _token(client, username, rol, **ambito):
    datos = {"username": username, "password": PASSWORD, "nombre_completo": username.title(), "rol": rol, **ambito}
    r = client.post("/api/auth/register", json=datos)
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _alumno(i, escuela="ESC-07", grado=2, ugel="UGEL San Martin", lejos=False, juntos=True):
    return {
        "alumno_id": f"P-{i:03d}", "escuela_id": escuela, "ugel": ugel, "grado_secundaria": grado,
        "zona_escuela": "Rural", "sexo": "F" if i % 2 else "M", "edad": 14,
        "distancia_hogar_escuela_km": 9.0 if lejos else 1.0, "horas_trabajo_semanal": 12 if lejos else 0,
        "tiempo_desplazamiento": "Mas de 60 min" if lejos else "Menos de 15 min",
        "internet_hogar": "False" if lejos else "True", "beneficiario_juntos": "True" if juntos else "False",
        "faltas_trimestre_1": 3, "faltas_trimestre_2": 5, "nota_trimestre_1_0_20": 12, "nota_trimestre_2_0_20": 11,
    }


def _csv(filas):
    columnas = list(filas[0].keys())
    lineas = [",".join(columnas)] + [",".join(str(f.get(c, "")) for c in columnas) for f in filas]
    return io.BytesIO("\n".join(lineas).encode("utf-8"))


# ---------------------------------------------------------------------------
# Alta individual -> predicción inmediata
# ---------------------------------------------------------------------------

def test_alta_docente_predice_y_fija_su_ambito(client):
    h = _token(client, "doc.uno", "docente", escuela_id="esc-07", grado_secundaria=2)
    datos = _alumno(1, escuela="OTRA", grado=5, lejos=True)
    r = client.post("/api/datos/alumno", headers=h, json=datos)
    assert r.status_code == 200, r.text
    assert r.json()["predicciones"]["calculadas"] == 1

    pred = client.get("/api/predicciones", headers=h).json()
    assert pred["con_prediccion"] == 1
    alumno = pred["tablas"]["alumnos"][0]
    # el ámbito sale del token, no del cuerpo
    assert alumno["alumno_id"] == "P-001"
    assert alumno["necesidad"] == "alta" and alumno["abandono"] == "alto"
    assert alumno["factores"], "debe explicar los factores"
    # nunca se usa el sexo para explicar
    assert all("sexo" not in (f["texto"] or "").lower() for f in alumno["factores"])


def test_docente_no_recibe_porcentajes_individuales(client):
    h = _token(client, "doc.uno", "docente", escuela_id="ESC-07", grado_secundaria=2)
    for i in range(3):
        client.post("/api/datos/alumno", headers=h, json=_alumno(i, lejos=bool(i % 2)))
    pred = client.get("/api/predicciones", headers=h).json()
    for a in pred["tablas"]["alumnos"]:
        assert not any(k.startswith("prob") or k.endswith("_pct") for k in a), a
    ids = [a["alumno_id"] for a in pred["tablas"]["alumnos"]]
    assert ids == sorted(ids), "orden por código, sin ranking"
    vista = client.get("/api/panel", headers=h).json()
    texto = str(vista["avisos_predictivos"])
    assert "prob_" not in texto


def test_factores_solo_si_se_sugiere_revision(client):
    h = _token(client, "doc.uno", "docente", escuela_id="ESC-07", grado_secundaria=2)
    client.post("/api/datos/alumno", headers=h, json=_alumno(1, lejos=True))
    client.post("/api/datos/alumno", headers=h, json=_alumno(2, lejos=False))
    alumnos = {a["alumno_id"]: a for a in client.get("/api/predicciones", headers=h).json()["tablas"]["alumnos"]}
    assert alumnos["P-001"]["sugerir_revision"] and alumnos["P-001"]["factores"]
    assert not alumnos["P-002"]["sugerir_revision"] and alumnos["P-002"]["factores"] == []


def test_secciones_ordenadas_por_interes_del_rol(client):
    h = _token(client, "doc.uno", "docente", escuela_id="ESC-07", grado_secundaria=2)
    for i in range(6):
        client.post("/api/datos/alumno", headers=h, json=_alumno(i, lejos=i < 2))
    secciones = client.get("/api/predicciones", headers=h).json()["secciones"]
    orden = {"alta": 0, "media": 1, "baja": 2}
    assert [orden[s["interes"]] for s in secciones] == sorted(orden[s["interes"]] for s in secciones)
    beca = next(s for s in secciones if s["id"] == "beca")
    assert beca["interes"] == "baja" and secciones[-1]["id"] == "beca"
    abandono = next(s for s in secciones if s["id"] == "abandono")
    assert abandono["frases"][0].startswith("El 33,3 % de tu clase tiene una probabilidad alta de abandonar")


# ---------------------------------------------------------------------------
# Importación CSV (director) y k-anonimato
# ---------------------------------------------------------------------------

def test_director_importa_csv_y_ve_desglose_por_grado_con_k_anonimato(client):
    h = _token(client, "dir.uno", "director", escuela_id="ESC-07")
    filas = [_alumno(i, grado=1, lejos=i < 2) for i in range(6)] + [_alumno(10 + i, grado=3) for i in range(2)]
    r = client.post("/api/datos/importar-csv", headers=h, files={"file": ("a.csv", _csv(filas), "text/csv")})
    assert r.status_code == 200, r.text
    assert r.json()["predicciones"]["calculadas"] == 8

    pred = client.get("/api/predicciones", headers=h).json()
    grados = pred["tablas"]["grados"]
    assert [g["label"] for g in grados["grupos"]] == ["1.º"]
    assert grados["ocultos"] == ["3.º"]
    assert "alumnos" not in pred["tablas"]
    assert pred["secciones"][0]["interes"] == "alta"


def test_director_no_puede_pisar_estudiantes_de_otra_escuela(client):
    h1 = _token(client, "dir.uno", "director", escuela_id="ESC-07")
    h2 = _token(client, "dir.dos", "director", escuela_id="ESC-99")
    client.post("/api/datos/alumno", headers=h1, json=_alumno(1))
    r = client.post("/api/datos/pegar", headers=h2, json={"data_text": "alumno_id,grado_secundaria\nP-001,2"})
    assert r.status_code == 200
    assert r.json()["rechazados"], "debe rechazar el estudiante de otra escuela"
    assert client.get("/api/predicciones", headers=h2).json()["total"] == 0


# ---------------------------------------------------------------------------
# Delegado: UGEL sin distinguir mayúsculas, rechazo de otras UGEL, simulador
# ---------------------------------------------------------------------------

def test_delegado_ugel_sin_distinguir_mayusculas_y_como_vamos(client):
    hd = _token(client, "dir.uno", "director", escuela_id="ESC-07")
    client.post("/api/datos/importar-csv", headers=hd,
                files={"file": ("a.csv", _csv([_alumno(i, lejos=i < 3) for i in range(6)]), "text/csv")})
    # el registro guarda «UGEL SAN MARTIN» en mayúsculas; el CSV trae «UGEL San Martin»
    h = _token(client, "del.uno", "delegado", ugel="ugel san martin")
    panel = client.get("/api/dashboard", headers=h).json()
    assert panel["hay_datos"] is True
    assert panel["tablas"]["escuelas"][0]["escuela_id"] == "ESC-07"
    pred = client.get("/api/predicciones", headers=h).json()
    assert pred["total"] == 6 and pred["tablas"]["escuelas"]["grupos"]


def test_delegado_rechaza_filas_de_otra_ugel(client):
    h = _token(client, "del.uno", "delegado", ugel="UGEL Cusco")
    filas = [_alumno(1, ugel="UGEL Cusco"), _alumno(2, ugel="UGEL Puno")]
    r = client.post("/api/datos/importar-csv", headers=h, files={"file": ("a.csv", _csv(filas), "text/csv")})
    cuerpo = r.json()
    assert cuerpo["creados"] == 1 and len(cuerpo["rechazados"]) == 1


def test_simulador_usa_datos_reales_y_moneda_configurable(client, monkeypatch):
    monkeypatch.setenv("DONPROFESOR_MONEDA", "PEN")
    hd = _token(client, "dir.uno", "director", escuela_id="ESC-07")
    client.post("/api/datos/importar-csv", headers=hd,
                files={"file": ("a.csv", _csv([_alumno(i, lejos=i < 2) for i in range(6)]), "text/csv")})
    h = _token(client, "del.uno", "delegado", ugel="UGEL San Martin")
    r = client.post("/api/simular-subvencion", headers=h,
                    json={"presupuesto_total": 1000, "pct_transporte": 50, "pct_beca": 25, "pct_refuerzo": 25})
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["moneda"] == "PEN" and datos["total"] == 6
    transporte = next(l for l in datos["lineas"] if l["linea"] == "transporte")
    assert transporte["estudiantes"] == 2 and transporte["importe"] == 500


# ---------------------------------------------------------------------------
# Modelo no disponible: nunca se inventan predicciones
# ---------------------------------------------------------------------------

def test_sin_modelo_las_predicciones_quedan_pendientes(client, monkeypatch, tmp_path):
    predictor.set_bundle_for_tests(None)
    monkeypatch.setenv("DONPROFESOR_MODEL_PATH", str(tmp_path / "no_existe.joblib"))
    h = _token(client, "doc.uno", "docente", escuela_id="ESC-07", grado_secundaria=2)
    r = client.post("/api/datos/alumno", headers=h, json=_alumno(1))
    assert r.status_code == 200
    assert r.json()["predicciones"]["pendientes"] == 1
    pred = client.get("/api/predicciones", headers=h).json()
    assert pred["modelo"]["disponible"] is False
    assert pred["con_prediccion"] == 0 and pred["secciones"] == []
    assert client.post("/api/predicciones/recalcular", headers=h).status_code == 503
    assert client.get("/api/modelo/campos", headers=h).status_code == 503

    # cuando vuelve el modelo, se calculan las pendientes
    predictor.set_bundle_for_tests(_bundle())
    r = client.post("/api/predicciones/recalcular?solo_pendientes=true", headers=h)
    assert r.status_code == 200 and r.json()["calculadas"] == 1


# ---------------------------------------------------------------------------
# Acciones y endpoints retirados
# ---------------------------------------------------------------------------

def test_acciones_solo_sobre_estudiantes_del_ambito(client):
    h1 = _token(client, "doc.uno", "docente", escuela_id="ESC-07", grado_secundaria=2)
    h2 = _token(client, "doc.dos", "docente", escuela_id="ESC-07", grado_secundaria=3)
    client.post("/api/datos/alumno", headers=h1, json=_alumno(1, lejos=True))
    ok = client.post("/api/acciones", headers=h1, json={"alumno_id": "P-001", "decision_tomada": "Tutoría"})
    assert ok.status_code == 200
    ajeno = client.post("/api/acciones", headers=h2, json={"alumno_id": "P-001", "decision_tomada": "Tutoría"})
    assert ajeno.status_code == 404
    assert client.post("/api/acciones", headers=h1, json={"decision_tomada": "x"}).status_code == 422


def test_endpoints_peligrosos_retirados(client):
    h = _token(client, "doc.uno", "docente", escuela_id="ESC-07", grado_secundaria=2)
    assert client.post("/api/mcp/read-query", headers=h, json={"sql_query": "SELECT 1"}).status_code in (404, 405)
    assert client.post("/api/config/llm", headers=h, json={"base_url": "http://evil"}).status_code in (404, 405)
    assert client.get("/api/predicciones").status_code == 401


def test_campos_del_modelo_para_el_formulario(client):
    h = _token(client, "doc.uno", "docente", escuela_id="ESC-07", grado_secundaria=2)
    campos = client.get("/api/modelo/campos", headers=h).json()
    assert campos["categoricas"]["tiempo_desplazamiento"][0] == "Menos de 15 min"
    assert "beneficiario_juntos" in campos["binarias"]
