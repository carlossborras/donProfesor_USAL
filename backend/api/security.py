"""
DONPROFESOR (#Hack4Edu 2026, Reto 13) · Seguridad de la API.

- Contraseñas: PBKDF2-HMAC-SHA256 (600 000 iteraciones, sal aleatoria). Solo librería estándar,
  sin dependencias nuevas. Las contraseñas antiguas en texto plano se aceptan una única vez y se
  re-cifran automáticamente al iniciar sesión (migración transparente).
- Tokens JWT (HS256) con rol y ámbito (escuela, grado, UGEL); caducan a las 8 horas.
- Dependencias FastAPI:
    * get_current_user -> 401 si falta el token o no es válido.
    * require_role(...) -> 403 si el rol del token no tiene permiso.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, Tuple

import jwt
from fastapi import Depends, Header, HTTPException

log = logging.getLogger("donprofesor.security")

ROLES = ("docente", "director", "delegado")
JWT_ALG = "HS256"
PBKDF2_PREFIX = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000

# Secretos de ejemplo que nunca deben usarse para firmar tokens reales
_SECRETOS_DEBILES = {
    "",
    "hack4edu-donprofesor-secret-key-2026",
    "cambia_esto",
    "cambia_esto_por_una_cadena_aleatoria_larga",
}
_jwt_secret_cache: Optional[str] = None


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

def get_jwt_secret() -> str:
    """Lee DONPROFESOR_JWT_SECRET (perezoso, para respetar el .env cargado por api/main.py).

    Si no existe o es un valor de ejemplo, se genera uno aleatorio en memoria: la app funciona,
    pero las sesiones caducan al reiniciar el servidor.
    """
    global _jwt_secret_cache
    if _jwt_secret_cache is None:
        secreto = os.environ.get("DONPROFESOR_JWT_SECRET", "").strip()
        if secreto in _SECRETOS_DEBILES or len(secreto) < 32:
            log.warning(
                "DONPROFESOR_JWT_SECRET no definido o demasiado débil: se usa un secreto aleatorio "
                "temporal (las sesiones caducarán al reiniciar). Genera uno con: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
            secreto = secrets.token_urlsafe(48)
        _jwt_secret_cache = secreto
    return _jwt_secret_cache


def get_jwt_expire_hours() -> int:
    try:
        return max(1, min(24, int(os.environ.get("DONPROFESOR_JWT_EXPIRE_HOURS", "8"))))
    except ValueError:
        return 8


# ---------------------------------------------------------------------------
# Contraseñas
# ---------------------------------------------------------------------------

def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    derivada = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{PBKDF2_PREFIX}${iterations}${_b64e(salt)}${_b64e(derivada)}"


def verify_password(password: str, stored: Optional[str]) -> Tuple[bool, bool]:
    """Devuelve (es_valida, hay_que_recifrar)."""
    if not stored:
        return False, False
    if stored.startswith(PBKDF2_PREFIX + "$"):
        try:
            _, iteraciones, salt_b64, hash_b64 = stored.split("$")
            iteraciones = int(iteraciones)
            salt, esperado = _b64d(salt_b64), _b64d(hash_b64)
        except (ValueError, TypeError):
            return False, False
        calculado = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iteraciones)
        valida = hmac.compare_digest(calculado, esperado)
        return valida, valida and iteraciones < PBKDF2_ITERATIONS
    # Compatibilidad: usuarios antiguos guardados en texto plano -> se re-cifran al entrar
    valida = hmac.compare_digest(password.encode("utf-8"), stored.encode("utf-8"))
    return valida, valida


_HASH_SENUELO = hash_password(secrets.token_urlsafe(16))


def burn_password_check(password: str) -> None:
    """Calcula un hash igualmente cuando el usuario no existe (mismo tiempo de respuesta)."""
    verify_password(password, _HASH_SENUELO)


# ---------------------------------------------------------------------------
# Tokens JWT
# ---------------------------------------------------------------------------

def create_access_token(user_row: Dict[str, Any]) -> str:
    ahora = datetime.now(timezone.utc)
    grado = user_row.get("grado_secundaria")
    payload = {
        "sub": user_row["username"],
        "username": user_row["username"],
        "nombre_completo": user_row.get("nombre_completo"),
        "rol": user_row["rol"],
        "escuela_id": user_row.get("escuela_id"),
        "grado_secundaria": int(grado) if grado not in (None, "") else None,
        "ugel": user_row.get("ugel"),
        "titulo_cargo": user_row.get("titulo_cargo"),
        "db_role": f"role_{user_row['rol']}",
        "iat": int(ahora.timestamp()),
        "exp": int((ahora + timedelta(hours=get_jwt_expire_hours())).timestamp()),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALG)


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(
        token,
        get_jwt_secret(),
        algorithms=[JWT_ALG],
        options={"require": ["exp", "sub"]},
    )


def _no_autenticado(detalle: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detalle, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Valida el JWT del encabezado Authorization (401 si falta, está mal o ha caducado)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _no_autenticado("Inicia sesión para continuar.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise _no_autenticado("Tu sesión ha caducado. Vuelve a iniciar sesión.") from None
    except jwt.PyJWTError:
        raise _no_autenticado("Sesión no válida. Vuelve a iniciar sesión.") from None
    if claims.get("rol") not in ROLES:
        raise _no_autenticado("Sesión no válida. Vuelve a iniciar sesión.")
    claims.setdefault("username", claims.get("sub"))
    return claims


def require_role(*roles: str) -> Callable[..., Dict[str, Any]]:
    """Dependencia: solo deja pasar a los roles indicados (403 para el resto)."""

    def _dependencia(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if user.get("rol") not in roles:
            raise HTTPException(
                status_code=403,
                detail="Tu rol no tiene acceso a este recurso.",
            )
        return user

    return _dependencia
