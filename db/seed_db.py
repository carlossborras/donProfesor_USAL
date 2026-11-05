"""
DONPROFESOR (#Hack4Edu 2026, Reto 13) · Inicializador de Base de Datos Real.
Crea el esquema con las 37 variables oficiales y los usuarios de acceso institucional de demostración
(contraseñas guardadas con hash; nuevas cuentas desde POST /api/auth/register).
Deja la tabla principal `alumnos_hack4edu` completamente vacía (0 registros), lista
para recibir los datos reales del reto y las salidas del modelo predictivo.
"""

from __future__ import annotations
import os
import sqlite3
from pathlib import Path
from typing import Optional

DB_DIR = Path(__file__).resolve().parent
SQLITE_PATH = DB_DIR / "donprofesor.db"
SCHEMA_SQL = DB_DIR / "schema.sql"
VIEWS_SQL = DB_DIR / "views_and_grants.sql"


def get_sqlite_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SQLITE_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


_COLUMNAS_OBLIGATORIAS = {"alumno_id", "escuela_id", "grado_secundaria"}
_inicializada: set = set()


def _definicion_alumnos() -> str:
    texto = SCHEMA_SQL.read_text(encoding="utf-8")
    inicio = texto.index("CREATE TABLE IF NOT EXISTS alumnos_hack4edu")
    return texto[inicio: texto.index(");", inicio) + 2]


def _migrar_tabla_alumnos(conn: sqlite3.Connection) -> None:
    """Lleva una tabla `alumnos_hack4edu` antigua al esquema actual sin perder datos.

    - Añade las columnas nuevas (salidas del modelo, fecha de alta...).
    - Si quedan restricciones NOT NULL en variables que pueden faltar (p. ej. notas de un alumno recién
      matriculado), reconstruye la tabla copiando los datos.
    """
    cur = conn.cursor()
    info = cur.execute("PRAGMA table_info(alumnos_hack4edu);").fetchall()
    actuales = {fila[1]: fila for fila in info}
    nuevo = sqlite3.connect(":memory:")
    nuevo.execute(_definicion_alumnos())
    esperadas = [fila[1] for fila in nuevo.execute("PRAGMA table_info(alumnos_hack4edu);").fetchall()]
    nuevo.close()

    sobran_not_null = [c for c, fila in actuales.items() if fila[3] and c not in _COLUMNAS_OBLIGATORIAS and fila[5] == 0]
    if sobran_not_null:
        comunes = [c for c in esperadas if c in actuales]
        lista = ", ".join(comunes)
        cur.executescript(
            "DROP VIEW IF EXISTS vista_docente; DROP VIEW IF EXISTS vista_director; "
            "DROP VIEW IF EXISTS vista_delegado; DROP VIEW IF EXISTS vista_avisos_predictivos; "
            "ALTER TABLE alumnos_hack4edu RENAME TO alumnos_hack4edu_antigua;"
        )
        cur.execute(_definicion_alumnos())
        cur.execute(f"INSERT INTO alumnos_hack4edu ({lista}) SELECT {lista} FROM alumnos_hack4edu_antigua;")
        cur.execute("DROP TABLE alumnos_hack4edu_antigua;")
        conn.commit()
        return

    for columna in esperadas:
        if columna not in actuales:
            cur.execute(f"ALTER TABLE alumnos_hack4edu ADD COLUMN {columna};")
    conn.commit()


def ensure_database() -> None:
    """Inicializa la base de datos una sola vez por proceso (evita repetirlo en cada consulta)."""
    clave = str(SQLITE_PATH)
    if clave not in _inicializada or not SQLITE_PATH.exists():
        init_and_seed_database(force_reset=False)
        _inicializada.add(clave)


def init_and_seed_database(force_reset: bool = False) -> None:
    """
    Inicializa la base de datos con la estructura de 37 variables y usuarios de autenticación.
    No inserta alumnos falsos ni simulaciones: queda lista para importación real.
    """
    if force_reset and SQLITE_PATH.exists():
        try:
            SQLITE_PATH.unlink()
        except Exception:
            pass

    conn = get_sqlite_connection()
    cur = conn.cursor()

    # Ejecutar esquema de tablas y vistas
    cur.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))

    # Migración idempotente: bases de datos creadas con el esquema anterior
    _migrar_tabla_alumnos(conn)

    cur.executescript(VIEWS_SQL.read_text(encoding="utf-8"))

    # Usuarios de demostración (contraseña: donprofesor2026), guardados con hash PBKDF2-SHA256.
    # INSERT OR IGNORE: nunca sobrescribe cuentas existentes (ni las registradas desde la web
    # ni la contraseña re-cifrada de usuarios antiguos).
    usuarios_demo = [
        (
            "docente",
            "pbkdf2_sha256$600000$AGiEME8rGzgIXb79kqJ2MA$S9HKNflVaCEQo3XGJxHALdjOV8AT-5-19DgRmr9X8dY",
            "Prof. Carmen Morales",
            "docente",
            "ESC-01",
            2,
            "UGEL-01-NORTE",
            "Tutoría 2º de Secundaria · I.E. San Juan Bautista",
        ),
        (
            "director",
            "pbkdf2_sha256$600000$rSPVrEDjRDSoysywAS3ynw$3PHX73vpdOWdLVIF5qbSqUHuuRJWxc6TG4Uw7YqgTtw",
            "Dr. Roberto Mendoza",
            "director",
            "ESC-01",
            None,
            "UGEL-01-NORTE",
            "Dirección de Centro · I.E. San Juan Bautista",
        ),
        (
            "delegado",
            "pbkdf2_sha256$600000$0BD41QBCjCSuAqpv6NYBkQ$SI4mpipIs11dA1ToElsPg1SBNxLBMo-s-yElyDM-Boo",
            "Lic. Sofía Herrera",
            "delegado",
            None,
            None,
            "UGEL-01-NORTE",
            "Especialista de Gestión Pedagógica · UGEL-01-NORTE",
        ),
    ]

    # En un despliegue público conviene desactivarlos: DONPROFESOR_CREAR_USUARIOS_DEMO=0
    if os.environ.get("DONPROFESOR_CREAR_USUARIOS_DEMO", "1").strip().lower() in ("0", "false", "no"):
        usuarios_demo = []

    cur.executemany(
        """
        INSERT OR IGNORE INTO usuario_plataforma
        (username, password_hash, nombre_completo, rol, escuela_id, grado_secundaria, ugel, titulo_cargo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        usuarios_demo,
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_and_seed_database(force_reset=True)
    print("Base de datos inicializada vacía en:", SQLITE_PATH)
    conn = get_sqlite_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM alumnos_hack4edu;")
    print(f"Registros en alumnos_hack4edu: {c.fetchone()[0]} (Base de datos limpia y lista para datos reales)")
    conn.close()
