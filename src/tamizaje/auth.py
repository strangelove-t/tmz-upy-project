"""Contraseña local única con scrypt de la biblioteca estándar.

Formato autocontenido: ``scrypt$n$r$p$sal_hex$digest_hex``. La verificación sólo
acepta los parámetros fijos de esta versión para que un secreto manipulado no
pueda forzar un consumo de memoria arbitrario.
"""

import hashlib
import hmac
import secrets

N, R, P = 2**14, 8, 1
SALT_BYTES = 16
DIGEST_BYTES = 32
MINIMUM_LENGTH = 12


def _derive(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=N, r=R, p=P, dklen=DIGEST_BYTES
    )


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    if len(password) < MINIMUM_LENGTH:
        raise ValueError(
            f"La contraseña debe tener al menos {MINIMUM_LENGTH} caracteres."
        )
    salt = salt if salt is not None else secrets.token_bytes(SALT_BYTES)
    if len(salt) != SALT_BYTES:
        raise ValueError(f"La sal debe tener {SALT_BYTES} bytes.")
    return f"scrypt${N}${R}${P}${salt.hex()}${_derive(password, salt).hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Nunca lanza excepciones: cualquier formato inesperado es un rechazo."""
    try:
        algorithm, n, r, p, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "scrypt" or (int(n), int(r), int(p)) != (N, R, P):
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        if len(salt) != SALT_BYTES or len(expected) != DIGEST_BYTES:
            return False
        return hmac.compare_digest(_derive(password, salt), expected)
    except (ValueError, TypeError, AttributeError, MemoryError):
        return False
