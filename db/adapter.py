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
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, text
from db.seed_db import get_sqlite_connection, init_and_seed_database, SQLITE_PATH


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
                else f"Semilla Provisional Local ({SQLITE_PATH.name})"
            ),
            "note": (
                "Modo Provisional Activo: listo para conectar con la BD definitiva del equipo mediante DATABASE_URL."
                if self.mode == "PROVISIONAL_SQLITE_SEED"
                else "Conectado a Base de Datos PostgreSQL externa del equipo."
            ),
        }

    def fetch_all(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        if self.mode == "EXTERNAL_POSTGRESQL" and self.engine is not None:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql))
                return [dict(row._mapping) for row in result.fetchall()]
        else:
            init_and_seed_database(force_reset=False)
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
            with self.engine.begin() as conn:
                conn.execute(text(sql))
        else:
            init_and_seed_database(force_reset=False)
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            conn.close()


db_adapter = DatabaseAdapter()
