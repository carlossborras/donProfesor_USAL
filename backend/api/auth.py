"""
DONPROFESOR (#Hack4Edu 2026, Reto 13) · Registro e inicio de sesión.

Endpoints:
  POST /api/auth/register          -> crea la cuenta (rol + ámbito) y devuelve la sesión (201)
  POST /api/auth/login             -> devuelve {access_token, token_type, user}
  GET  /api/auth/me                -> datos del usuario de la sesión actual
  GET  /api/auth/opciones-registro -> roles, escuelas/UGEL conocidas y si cada rol pide código

Ámbito obligatorio según el rol (es lo que limita lo que verá cada persona):
  docente  -> escuela_id + grado_secundaria
  director -> escuela_id
  delegado -> ugel

Códigos de invitación (opcionales, por variable de entorno):
  DONPROFESOR_CODIGO_REGISTRO_DOCENTE / _DIRECTOR / _DELEGADO
  Si una variable está definida, registrarse con ese rol exige el código. Si no, el registro es libre.
"""

from __future__ import annotations

import hmac
import os
import re
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from api.security import (
    ROLES,
    burn_password_check,
    create_access_token,
    get_current_user,
    get_jwt_expire_hours,
    hash_password,
    verify_password,
)
from db.adapter import db_adapter

router = APIRouter(prefix="/api/auth", tags=["auth"])

USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,40}$")
CODIGO_RE = re.compile(r"^[A-Za-z0-9 _.\-ºª°]{1,80}$")

CARGO_POR_DEFECTO = {
    "docente": "Docente tutor/a",
    "director": "Dirección de centro educativo",
    "delegado": "Especialista de gestión pedagógica (UGEL)",
}

_SQL_USUARIO = (
    "SELECT username, password_hash, nombre_completo, rol, escuela_id, grado_secundaria, ugel, titulo_cargo "
    "FROM usuario_plataforma WHERE username = ?;"
)


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=200)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=8, max_length=200)
    nombre_completo: str = Field(min_length=3, max_length=120)
    rol: Literal["docente", "director", "delegado"]
    escuela_id: Optional[str] = Field(default=None, max_length=32)
    grado_secundaria: Optional[int] = Field(default=None, ge=1, le=5)
    ugel: Optional[str] = Field(default=None, max_length=80)
    titulo_cargo: Optional[str] = Field(default=None, max_length=140)
    codigo_invitacion: Optional[str] = Field(default=None, max_length=120)

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        v = v.strip().lower()
        if not USERNAME_RE.match(v):
            raise ValueError("El usuario solo puede tener minúsculas, números, punto, guion y guion bajo (3 a 40).")
        return v

    @field_validator("nombre_completo", "titulo_cargo")
    @classmethod
    def _texto(cls, v: Optional[str]) -> Optional[str]:
        return " ".join(v.split()) if v else v

    @field_validator("escuela_id", "ugel")
    @classmethod
    def _codigo(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        v = " ".join(v.split()).upper()
        if not CODIGO_RE.match(v):
            raise ValueError("Código de escuela o UGEL con caracteres no válidos.")
        return v

    @model_validator(mode="after")
    def _reglas(self) -> "RegisterRequest":
        pwd = self.password
        if not re.search(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]", pwd) or not re.search(r"\d", pwd):
            raise ValueError("La contraseña debe tener al menos 8 caracteres, con letras y números.")
        if self.username in pwd.lower():
            raise ValueError("La contraseña no puede contener el nombre de usuario.")
        if self.rol == "docente":
            if not self.escuela_id or not self.grado_secundaria:
                raise ValueError("Un docente debe indicar su escuela y su grado (1.º a 5.º de secundaria).")
            self.ugel = self.ugel or None
        elif self.rol == "director":
            if not self.escuela_id:
                raise ValueError("Un director debe indicar su escuela.")
            self.grado_secundaria = None
        else:  # delegado
            if not self.ugel:
                raise ValueError("Un delegado debe indicar su UGEL.")
            self.escuela_id = None
            self.grado_secundaria = None
        return self


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def public_user(row: Dict[str, Any]) -> Dict[str, Any]:
    """Datos del usuario que se pueden enviar al navegador (nunca el hash)."""
    grado = row.get("grado_secundaria")
    return {
        "username": row["username"],
        "nombre_completo": row.get("nombre_completo"),
        "rol": row["rol"],
        "db_role": f"role_{row['rol']}",
        "escuela_id": row.get("escuela_id"),
        "grado_secundaria": int(grado) if grado not in (None, "") else None,
        "ugel": row.get("ugel"),
        "titulo_cargo": row.get("titulo_cargo"),
    }


def _sesion(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "access_token": create_access_token(row),
        "token_type": "bearer",
        "expires_in": get_jwt_expire_hours() * 3600,
        "user": public_user(row),
    }


def _codigo_requerido(rol: str) -> Optional[str]:
    valor = os.environ.get(f"DONPROFESOR_CODIGO_REGISTRO_{rol.upper()}", "").strip()
    return valor or None


def _buscar_usuario(username: str) -> Optional[Dict[str, Any]]:
    return db_adapter.fetch_one(_SQL_USUARIO, (username,))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", status_code=201, summary="Crear una cuenta (docente, director o delegado)")
def register(req: RegisterRequest) -> Dict[str, Any]:
    codigo = _codigo_requerido(req.rol)
    if codigo and not hmac.compare_digest((req.codigo_invitacion or "").strip(), codigo):
        raise HTTPException(status_code=403, detail="El código de invitación para este rol no es válido.")

    if _buscar_usuario(req.username):
        raise HTTPException(status_code=409, detail="Ese nombre de usuario ya está en uso.")

    fila = {
        "username": req.username,
        "nombre_completo": req.nombre_completo,
        "rol": req.rol,
        "escuela_id": req.escuela_id,
        "grado_secundaria": req.grado_secundaria,
        "ugel": req.ugel,
        "titulo_cargo": req.titulo_cargo or CARGO_POR_DEFECTO[req.rol],
    }
    try:
        db_adapter.execute_write(
            """
            INSERT INTO usuario_plataforma
            (username, password_hash, nombre_completo, rol, escuela_id, grado_secundaria, ugel, titulo_cargo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                fila["username"],
                hash_password(req.password),
                fila["nombre_completo"],
                fila["rol"],
                fila["escuela_id"],
                fila["grado_secundaria"],
                fila["ugel"],
                fila["titulo_cargo"],
            ),
        )
    except Exception:  # p. ej. dos registros simultáneos con el mismo usuario
        if _buscar_usuario(req.username):
            raise HTTPException(status_code=409, detail="Ese nombre de usuario ya está en uso.") from None
        raise
    return _sesion(fila)


@router.post("/login", summary="Iniciar sesión")
def login(req: LoginRequest) -> Dict[str, Any]:
    username = req.username.strip().lower()
    fila = _buscar_usuario(username)
    if not fila:
        burn_password_check(req.password)
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")

    valida, recifrar = verify_password(req.password, fila.get("password_hash"))
    if not valida or fila.get("rol") not in ROLES:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")

    if recifrar:
        db_adapter.execute_write(
            "UPDATE usuario_plataforma SET password_hash = ? WHERE username = ?;",
            (hash_password(req.password), username),
        )
    return _sesion(fila)


@router.get("/me", summary="Usuario de la sesión actual")
def me(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    fila = _buscar_usuario(user["sub"])
    if not fila or fila.get("rol") != user.get("rol"):
        raise HTTPException(status_code=401, detail="Tu cuenta ya no está disponible. Vuelve a iniciar sesión.")
    return {"user": public_user(fila)}


@router.get("/opciones-registro", summary="Opciones para el formulario de registro")
def opciones_registro() -> Dict[str, Any]:
    def _distintos(sql: str) -> List[str]:
        try:
            return sorted({r["v"] for r in db_adapter.fetch_all(sql) if r.get("v")})
        except Exception:
            return []

    escuelas = set(_distintos("SELECT DISTINCT escuela_id AS v FROM alumnos_hack4edu;"))
    escuelas |= set(_distintos("SELECT DISTINCT escuela_id AS v FROM usuario_plataforma;"))
    ugels = set(_distintos("SELECT DISTINCT ugel AS v FROM alumnos_hack4edu;"))
    ugels |= set(_distintos("SELECT DISTINCT ugel AS v FROM usuario_plataforma;"))
    return {
        "roles": [
            {"id": "docente", "label": "Docente", "ambito": "Tu grupo: escuela y grado"},
            {"id": "director", "label": "Director/a", "ambito": "Tu escuela, por grados"},
            {"id": "delegado", "label": "Delegado/a UGEL", "ambito": "Tu UGEL, por escuelas"},
        ],
        "escuelas": sorted(escuelas),
        "ugels": sorted(ugels),
        "grados": [1, 2, 3, 4, 5],
        "requiere_codigo": {rol: bool(_codigo_requerido(rol)) for rol in ROLES},
    }
