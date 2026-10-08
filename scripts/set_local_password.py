"""Crea o reemplaza la contraseña local de la aplicación.

Uso (desde la raíz del proyecto):

    .venv\\Scripts\\python.exe scripts\\set_local_password.py   (Windows)
    .venv/bin/python scripts/set_local_password.py             (Linux/macOS)

Sólo se guarda sal + hash scrypt en ``.streamlit/secrets.toml``, que Git ignora.
Nunca se imprime la contraseña ni el hash.
"""

import getpass
import os
import sys
from pathlib import Path

from tamizaje.auth import hash_password

SECRETS_PATH = Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml"


def write_secret(path: Path, password: str) -> None:
    encoded = hash_password(password)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f'[auth]\npassword_hash = "{encoded}"\n'
    # En POSIX el archivo se crea ya con 0600; en Windows chmod sólo controla
    # lectura/escritura y la protección depende de la cuenta del equipo.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(content)
    path.chmod(0o600)


def main() -> int:
    password = getpass.getpass("Nueva contraseña (mínimo 12 caracteres): ")
    confirmation = getpass.getpass("Confirma la contraseña: ")
    if password != confirmation:
        print("Las contraseñas no coinciden. No se hicieron cambios.")
        return 1
    try:
        write_secret(SECRETS_PATH, password)
    except ValueError as error:
        print(f"{error} No se hicieron cambios.")
        return 1
    print(f"Contraseña guardada en {SECRETS_PATH}.")
    print("Reinicia la aplicación para aplicar el cambio.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
