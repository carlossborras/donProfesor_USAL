#!/usr/bin/env python3
"""
DONPROFESOR · Reorganiza el repositorio en backend / frontend / ml / data / docs.

Uso (desde la raíz del repositorio, con el árbol de trabajo limpio):
    python3 reorganizar.py            # aplica los cambios
    python3 reorganizar.py --simular  # solo muestra lo que haría

Usa `git mv`, así que se conserva el historial de cada fichero. No hace commit: revisa,
prueba (`pixi run test`, `pixi run start`) y luego haz el commit tú.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SIMULAR = "--simular" in sys.argv
RAIZ = Path.cwd()

# (origen, destino). Los que no existan se avisan y se saltan.
MOVIMIENTOS = [
    ("api", "backend/api"),
    ("db", "backend/db"),
    ("model", "backend/model"),
    ("mcp_server", "backend/mcp_server"),
    ("scripts", "backend/scripts"),
    ("tests", "backend/tests"),
    ("web/app.py", "backend/run.py"),
    ("web/frontend", "frontend"),
    ("entrenadorModelo.py", "ml/entrenadorModelo.py"),
    ("modelo.joblib", "ml/modelo.joblib"),
    ("documentos", "docs"),
    ("Informe_breve_de_transferibilidad.docx", "docs/Informe_breve_de_transferibilidad.docx"),
]
BORRAR = ["main.py", "reorganizar.py"]  # main.py solo imprime «Hello from hack4edu!»; este script no hace falta después

# Cambios de texto: (fichero, [(texto_actual, texto_nuevo), ...]). Cada texto debe existir.
EDICIONES = {
    "backend/model/config.py": [
        ("ROOT_DIR = Path(__file__).resolve().parent.parent\n",
         "ROOT_DIR = Path(__file__).resolve().parents[2]  # raíz del repositorio (backend/model/config.py)\n"),
        ('return ROOT_DIR / "modelo.joblib"', 'return ROOT_DIR / "ml" / "modelo.joblib"'),
    ],
    "backend/api/main.py": [
        ('_env_path = Path(__file__).resolve().parent.parent / ".env"',
         '_env_path = Path(__file__).resolve().parents[2] / ".env"  # .env en la raíz del repositorio'),
        ("ROOT_DIR = Path(__file__).resolve().parent.parent\n",
         "ROOT_DIR = Path(__file__).resolve().parents[2]  # raíz del repositorio\n"),
        ('FRONTEND_DIR = ROOT_DIR / "web" / "frontend"', 'FRONTEND_DIR = ROOT_DIR / "frontend"'),
    ],
    "backend/run.py": [
        ("para que `uv run python web/app.py` o `python web/app.py` funcione desde cualquier directorio.",
         "para que `python backend/run.py` (o `pixi run start`) funcione desde cualquier directorio."),
        ("Soluciona la resolución de módulos añadiendo automáticamente la raíz del repositorio a `sys.path`",
         "Añade la carpeta backend/ a `sys.path`"),
        ("ROOT_DIR = Path(__file__).resolve().parent.parent\n", "ROOT_DIR = Path(__file__).resolve().parent  # backend/\n"),
    ],
    "backend/tests/test_donprofesor.py": [
        ("3. Frontend servido y web/app.py importable.", "3. Frontend servido y backend/run.py importable."),
        ("runpy.run_path('web/app.py', run_name='not_main')", "runpy.run_path('run.py', run_name='not_main')"),
    ],
    "backend/scripts/predicciones.py": [
        ("Ejemplos (desde la raíz del repositorio):\n"
         "  # Estado del modelo\n"
         "  pixi run python -m scripts.predicciones estado\n"
         "\n"
         "  # Recalcular las predicciones de TODOS los estudiantes (p. ej. tras reentrenar el modelo)\n"
         "  pixi run python -m scripts.predicciones recalcular\n"
         "  pixi run python -m scripts.predicciones recalcular --solo-pendientes\n"
         "\n"
         "  # Cargar un CSV en el ámbito de una escuela (igual que lo haría un director desde la web)\n"
         "  pixi run python -m scripts.predicciones cargar --csv data/muestra_30_alumnos_peru.csv --escuela ESC-01 --ugel \"UGEL Cusco\"\n",
         "Ejemplos (desde la raíz del repositorio):\n"
         "  pixi run modelo-estado                     # ¿se puede cargar el modelo?\n"
         "  pixi run recalcular                        # recalcula las predicciones de todos los estudiantes\n"
         "  pixi run recalcular --solo-pendientes\n"
         "\n"
         "  # Cargar un CSV en el ámbito de una escuela (igual que lo haría un director desde la web)\n"
         "  pixi run cargar-csv --csv data/muestra_30_alumnos_peru.csv --escuela ESC-01 --ugel \"UGEL Cusco\"\n"),
        ("    filas = students.leer_tabla(Path(args.csv).read_bytes())",
         "    ruta = Path(args.csv)\n"
         "    if not ruta.is_absolute() and not ruta.exists():\n"
         "        ruta = ROOT.parent / ruta  # rutas relativas a la raíz del repositorio\n"
         "    filas = students.leer_tabla(ruta.read_bytes())"),
    ],
    "pixi.toml": [
        ('build = "npm --prefix web/frontend run build"\n'
         'start = { cmd = "python web/app.py", depends-on = ["build"] }\n'
         'test = "pytest -v"\n'
         'seed = "python -m db.seed_db"\n'
         'train = "python entrenadorModelo.py"\n'
         'modelo-estado = "python -m scripts.predicciones estado"\n'
         'recalcular = "python -m scripts.predicciones recalcular"\n',
         'frontend-install = "npm --prefix frontend install"\n'
         'build = "npm --prefix frontend run build"\n'
         'start = { cmd = "python backend/run.py", depends-on = ["build"] }\n'
         'test = "pytest -v"\n'
         'seed = { cmd = "python -m db.seed_db", cwd = "backend" }\n'
         'train = { cmd = "python entrenadorModelo.py", cwd = "ml" }\n'
         'modelo-estado = { cmd = "python -m scripts.predicciones estado", cwd = "backend" }\n'
         'recalcular = { cmd = "python -m scripts.predicciones recalcular", cwd = "backend" }\n'
         'cargar-csv = { cmd = "python -m scripts.predicciones cargar", cwd = "backend" }\n'),
    ],
    "pyproject.toml": [
        ('pythonpath = ["."]', 'pythonpath = ["backend"]\ntestpaths = ["backend/tests"]'),
    ],
    "Dockerfile": [
        ("COPY web/frontend/package.json web/frontend/package-lock.json ./", "COPY frontend/package.json frontend/package-lock.json ./"),
        ("COPY web/frontend/ ./", "COPY frontend/ ./"),
        ("COPY db/ ./db/\nCOPY model/ ./model/\nCOPY scripts/ ./scripts/\nCOPY data/ ./data/\n"
         "COPY mcp_server/ ./mcp_server/\nCOPY api/ ./api/\nCOPY web/ ./web/\n"
         "COPY --from=frontend /frontend/dist ./web/frontend/dist\n",
         "COPY backend/ ./backend/\nCOPY data/ ./data/\nCOPY --from=frontend /frontend/dist ./frontend/dist\n"),
        ("COPY modelo.joblib ./modelo.joblib", "COPY ml/modelo.joblib ./ml/modelo.joblib"),
        ('CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]',
         'CMD ["uvicorn", "api.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]'),
    ],
    "docker-compose.yml": [
        ("./db/schema.sql:", "./backend/db/schema.sql:"),
        ("./db/views_and_grants.sql:", "./backend/db/views_and_grants.sql:"),
        ('DONPROFESOR_MODEL_PATH: "/app/modelo.joblib"', 'DONPROFESOR_MODEL_PATH: "/app/ml/modelo.joblib"'),
    ],
    ".dockerignore": [
        ("web/frontend/node_modules", "frontend/node_modules"),
        ("db/*.db", "backend/db/*.db"),
    ],
    ".gitignore": [
        ("db/donprofesor.db", "backend/db/donprofesor.db"),
        ("web/frontend/node_modules/", "frontend/node_modules/"),
    ],
    ".env.example": [
        ("SQLite local (db/donprofesor.db)", "SQLite local (backend/db/donprofesor.db)"),
        ("DONPROFESOR_MODEL_PATH=modelo.joblib", "DONPROFESOR_MODEL_PATH=ml/modelo.joblib"),
    ],
}

# README: sustituciones sueltas (sin exigirlas) + sección nueva con la estructura
README_SUSTITUCIONES = [
    ("pixi run npm --prefix web/frontend install", "pixi run frontend-install"),
    ("(deja el .joblib en la raíz)", "(se ejecuta en ml/)"),
    ("pixi run python -m scripts.predicciones recalcular --solo-pendientes", "pixi run recalcular --solo-pendientes"),
    ("pixi run python -m scripts.predicciones cargar", "pixi run cargar-csv"),
    ("`modelo.joblib`", "`ml/modelo.joblib`"),
    ("`entrenadorModelo.py`", "`ml/entrenadorModelo.py`"),
    ("(`db/students.py` -> `model/predictor.py`)", "(`backend/db/students.py` -> `backend/model/predictor.py`)"),
    ("web/frontend", "frontend"),
]
ESTRUCTURA = """## Estructura del repositorio

```
backend/            Servidor Python (FastAPI)
  api/              Endpoints: auth, paneles, predicciones, carga de datos
  db/               Esquema, vistas por rol, adaptador SQLite/PostgreSQL, alta de estudiantes
  model/            Motor de predicción: carga ml/modelo.joblib, predice y explica
  mcp_server/       Servidor MCP y agente del asistente «Lo hablamos»
  scripts/          Utilidades de línea de comandos (estado del modelo, recalcular, cargar CSV)
  tests/            Pruebas (pytest)
  run.py            Arranque del servidor (pixi run start)
frontend/           Aplicación React (Vite): src/, dist/ compilado
ml/                 Entrenamiento (entrenadorModelo.py) y modelo entrenado (modelo.joblib)
data/               CSV de ejemplo y dataset sintético
docs/               Documentación del reto
```

"""


def sh(*args: str) -> None:
    print("  $", " ".join(args))
    if not SIMULAR:
        subprocess.run(args, check=True)


def fallo(msg: str, deshacer: bool = False) -> None:
    print(f"\nERROR: {msg}")
    if deshacer:
        print("La reorganización ha quedado a medias. Para volver atrás: git reset --hard HEAD\n"
              "(las carpetas no versionadas ya movidas, como node_modules, se quedan en su sitio nuevo).")
    sys.exit(1)


def main() -> None:
    if not (RAIZ / ".git").exists() or not (RAIZ / "pixi.toml").exists():
        fallo("Ejecuta el script desde la raíz del repositorio (donde está pixi.toml).")
    if (RAIZ / "backend").exists():
        fallo("Ya existe la carpeta backend/: parece que el repositorio ya está reorganizado.")
    sucio = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True).stdout.strip()
    if sucio and not SIMULAR:
        fallo("Tienes cambios sin guardar. Haz commit o stash antes de reorganizar.\n" + sucio)

    print("1) Moviendo ficheros con git mv")
    for d in ("backend", "ml", "docs"):
        if not SIMULAR:
            (RAIZ / d).mkdir(exist_ok=True)
    for origen, destino in MOVIMIENTOS:
        if not (RAIZ / origen).exists():
            print(f"  (no existe {origen}, se salta)")
            continue
        if (RAIZ / destino).exists() and (RAIZ / destino).is_dir() and (RAIZ / origen).is_dir():
            # destino ya creado (p. ej. docs/): mover el contenido
            for hijo in sorted((RAIZ / origen).iterdir()):
                sh("git", "mv", str(Path(origen) / hijo.name), str(Path(destino) / hijo.name))
            continue
        sh("git", "mv", origen, destino)
    for f in BORRAR:
        if (RAIZ / f).exists():
            sh("git", "rm", "-q", f)
    # carpetas que quedan vacías (solo cachés o node_modules ya movidos)
    for vacia in ("web", "documentos"):
        p = RAIZ / vacia
        if p.exists() and not SIMULAR:
            restos = [x for x in p.rglob("*") if x.is_file() and "__pycache__" not in x.parts]
            if restos:
                print(f"  Aviso: {vacia}/ conserva ficheros no versionados: {[str(r) for r in restos][:5]}")
            else:
                shutil.rmtree(p)

    if SIMULAR:
        print("\n(simulación: no se han editado ficheros)")
        return

    print("2) Actualizando rutas en el código y la configuración")
    for fichero, cambios in EDICIONES.items():
        ruta = RAIZ / fichero
        if not ruta.exists():
            fallo(f"No existe {fichero}.", deshacer=True)
        texto = ruta.read_text(encoding="utf-8")
        for viejo, nuevo in cambios:
            if viejo not in texto:
                fallo(f"En {fichero} no encuentro el texto esperado:\n{viejo[:200]}", deshacer=True)
            texto = texto.replace(viejo, nuevo)
        ruta.write_text(texto, encoding="utf-8")
        print(f"  ✔ {fichero}")

    readme = RAIZ / "README.md"
    texto = readme.read_text(encoding="utf-8")
    for viejo, nuevo in README_SUSTITUCIONES:
        texto = texto.replace(viejo, nuevo)
    if "## Estructura del repositorio" not in texto and "## Acceso con cuenta" in texto:
        texto = texto.replace("## Acceso con cuenta", ESTRUCTURA + "## Acceso con cuenta", 1)
    readme.write_text(texto, encoding="utf-8")
    print("  ✔ README.md")

    for cache in RAIZ.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)

    print("""
Listo. Ahora:
  pixi run modelo-estado     # debe decir "disponible": true
  pixi run test              # todas en verde
  pixi run start             # http://localhost:8000
  git add -A && git status   # revisa: deben salir como «renamed»
""")


if __name__ == "__main__":
    main()
