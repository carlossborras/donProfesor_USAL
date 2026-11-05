"""
DONPROFESOR · Utilidad de línea de comandos para cargar estudiantes y (re)calcular predicciones
con el modelo del equipo (modelo.joblib, LightGBM + Random Forest).

Ejemplos (desde la raíz del repositorio):
  pixi run modelo-estado                     # ¿se puede cargar el modelo?
  pixi run recalcular                        # recalcula las predicciones de todos los estudiantes
  pixi run recalcular --solo-pendientes

  # Cargar un CSV en el ámbito de una escuela (igual que lo haría un director desde la web)
  pixi run cargar-csv --csv data/muestra_30_alumnos_peru.csv --escuela ESC-01 --ugel "UGEL Cusco"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import students  # noqa: E402
from db.adapter import db_adapter  # noqa: E402
from db.seed_db import ensure_database  # noqa: E402
from model import predictor  # noqa: E402


def _estado(_: argparse.Namespace) -> int:
    print(json.dumps(predictor.model_status(), ensure_ascii=False, indent=2))
    return 0


def _recalcular(args: argparse.Namespace) -> int:
    extra = " WHERE necesidad_intervencion IS NULL" if args.solo_pendientes else ""
    columnas = ", ".join(["alumno_id"] + sorted(students.ENTRADA - {"alumno_id"}))
    filas = db_adapter.fetch_all(f"SELECT {columnas} FROM alumnos_hack4edu{extra} ORDER BY alumno_id;")
    total = {"calculadas": 0, "pendientes": 0}
    for i in range(0, len(filas), 500):
        r = students._predecir_y_guardar(filas[i:i + 500], borrar_si_falla=False)
        total["calculadas"] += r["calculadas"]
        total["pendientes"] += r["pendientes"]
        if r.get("aviso"):
            print(r["aviso"], file=sys.stderr)
    print(f"Estudiantes: {len(filas)} · con predicción: {total['calculadas']} · pendientes: {total['pendientes']}")
    return 0 if total["pendientes"] == 0 else 1


def _cargar(args: argparse.Namespace) -> int:
    if not args.escuela:
        print("Indica --escuela.", file=sys.stderr)
        return 2
    usuario = {"rol": "director", "escuela_id": args.escuela, "ugel": args.ugel, "username": "cli", "sub": "cli"}
    ruta = Path(args.csv)
    if not ruta.is_absolute() and not ruta.exists():
        ruta = ROOT.parent / ruta  # rutas relativas a la raíz del repositorio
    filas = students.leer_tabla(ruta.read_bytes())
    resumen = students.guardar_alumnos(filas, usuario)
    print(json.dumps(resumen, ensure_ascii=False, indent=2, default=str))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="orden", required=True)
    sub.add_parser("estado", help="Muestra si el modelo está disponible")
    rec = sub.add_parser("recalcular", help="Recalcula las predicciones de todos los estudiantes")
    rec.add_argument("--solo-pendientes", action="store_true")
    car = sub.add_parser("cargar", help="Carga un CSV en una escuela y calcula sus predicciones")
    car.add_argument("--csv", required=True)
    car.add_argument("--escuela", required=True)
    car.add_argument("--ugel", default=None)
    args = parser.parse_args()
    ensure_database()
    return {"estado": _estado, "recalcular": _recalcular, "cargar": _cargar}[args.orden](args)


if __name__ == "__main__":
    raise SystemExit(main())
