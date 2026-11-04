"""
DONPROFESOR (#Hack4Edu) · Adaptador Desacoplado de Base de Datos (Provisional -> Definitiva).

Como la Base de Datos definitiva la está construyendo otro compañero del equipo:
1. Por defecto (`DB_MODE=PROVISIONAL_SEED`), utiliza la base de datos provisional pre-sembrada
   con las vistas `vista_docente`, `vista_director`, `vista_director_clima`, `vista_delegado` y `vista_avisos_predictivos`.
2. En cuanto el compañero entregue la Base de Datos PostgreSQL definitiva, basta con definir la variable
   de entorno `DATABASE_URL=postgresql://usuario:clave@host:5432/nombre_bd` y este adaptador redirige
   todas las consultas de la API y del Servidor MCP a PostgreSQL sin cambiar ni una línea de React ni de FastAPI.
"""

from __future__ import annotations
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import create_engine, text
import db.seed_db as _seed
from db.seed_db import get_sqlite_connection, init_and_seed_database, ensure_database


_PLACEHOLDER = re.compile(r"\?")


def _to_named_params(sql: str, params: tuple) -> Tuple[str, Dict[str, Any]]:
    """Convierte los marcadores '?' (estilo SQLite) en ':p0, :p1...' para SQLAlchemy/PostgreSQL.

    Así las mismas consultas parametrizadas funcionan en los dos motores (nunca se concatenan valores).
    """
    contador = iter(range(len(params)))
    sql_named = _PLACEHOLDER.sub(lambda _m: f":p{next(contador)}", sql) if params else sql
    return sql_named.rstrip().rstrip(";"), {f"p{i}": v for i, v in enumerate(params)}


class DatabaseAdapter:
    def __init__(self) -> None:
        self.database_url: Optional[str] = os.environ.get("DATABASE_URL")
        if self.database_url:
            self.mode = "EXTERNAL_POSTGRESQL"
            self.engine = create_engine(self.database_url, pool_pre_ping=True)
        else:
            self.mode = "PROVISIONAL_SQLITE_SEED"
            self.engine = None
            init_and_seed_database(force_reset=False)

    def get_status_metadata(self) -> Dict[str, Any]:
        return {
            "db_mode": self.mode,
            "is_provisional": self.mode == "PROVISIONAL_SQLITE_SEED",
            "connection_target": (
                self.database_url.split("@")[-1]
                if self.database_url
                else f"Semilla Provisional Local ({_seed.SQLITE_PATH.name})"
            ),
            "note": (
                "Modo Provisional Activo: listo para conectar con la BD definitiva del equipo mediante DATABASE_URL."
                if self.mode == "PROVISIONAL_SQLITE_SEED"
                else "Conectado a Base de Datos PostgreSQL externa del equipo."
            ),
        }

    def fetch_all(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        if self.mode == "EXTERNAL_POSTGRESQL" and self.engine is not None:
            sql_named, bind = _to_named_params(sql, params)
            with self.engine.connect() as conn:
                result = conn.execute(text(sql_named), bind)
                return [dict(row._mapping) for row in result.fetchall()]
        else:
            ensure_database()
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows

    def fetch_one(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def execute_write(self, sql: str, params: tuple = ()) -> None:
        if self.mode == "EXTERNAL_POSTGRESQL" and self.engine is not None:
            sql_named, bind = _to_named_params(sql, params)
            with self.engine.begin() as conn:
                conn.execute(text(sql_named), bind)
        else:
            ensure_database()
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            conn.close()

    def execute_query(self, sql: str, params: tuple = ()) -> None:
        """Alias compatible de execute_write para comandos DML/DDL."""
        self.execute_write(sql, params)


db_adapter = DatabaseAdapter()
