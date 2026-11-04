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

    # Migración idempotente para la columna docente_tutor si la tabla ya existía
    try:
        cur.execute("ALTER TABLE alumnos_hack4edu ADD COLUMN docente_tutor VARCHAR(60);")
    except Exception:
        pass

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
