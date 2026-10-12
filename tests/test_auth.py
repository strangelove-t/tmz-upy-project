import os
import stat
import tomllib
from pathlib import Path

import pytest

from scripts.set_local_password import write_secret
from tamizaje.auth import hash_password, verify_password

PASSWORD = "frase-segura-de-prueba"


def test_password_hash_round_trip_without_plaintext() -> None:
    encoded = hash_password(PASSWORD, salt=bytes(range(16)))

    assert PASSWORD not in encoded
    assert verify_password(PASSWORD, encoded)
    assert not verify_password("incorrecta", encoded)


def test_password_hash_uses_random_salt() -> None:
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_password_rejects_short_value_and_malformed_hash() -> None:
    with pytest.raises(ValueError, match="12 caracteres"):
        hash_password("corta")
    assert not verify_password("cualquier-clave", "valor-inválido")
    assert not verify_password("cualquier-clave", "")


@pytest.mark.parametrize(
    "tamper",
    [
        lambda parts: ["bcrypt", *parts[1:]],
        lambda parts: [parts[0], str(2**24), *parts[2:]],
        lambda parts: [*parts[:2], "64", *parts[3:]],
        lambda parts: [*parts[:3], "16", *parts[4:]],
        lambda parts: [*parts[:4], "zz", parts[5]],
        lambda parts: [*parts[:4], "", parts[5]],
        lambda parts: [*parts[:5], parts[5][:8]],
        lambda parts: [*parts[:5], "00" * 4096],
        lambda parts: [*parts, "extra"],
    ],
)
def test_verify_rejects_tampered_parameters_without_heavy_work(tamper) -> None:
    encoded = hash_password(PASSWORD, salt=bytes(range(16)))
    tampered = "$".join(tamper(encoded.split("$")))

    assert not verify_password(PASSWORD, tampered)


def test_write_secret_stores_only_verifiable_hash(tmp_path) -> None:
    target = tmp_path / ".streamlit" / "secrets.toml"
    write_secret(target, PASSWORD)

    content = target.read_text(encoding="utf-8")
    assert PASSWORD not in content
    encoded = tomllib.loads(content)["auth"]["password_hash"]
    assert verify_password(PASSWORD, encoded)


@pytest.mark.skipif(os.name != "posix", reason="permisos POSIX")
def test_write_secret_restricts_permissions(tmp_path) -> None:
    target = tmp_path / "secrets.toml"
    target.write_text("anterior", encoding="utf-8")
    target.chmod(0o644)

    write_secret(target, PASSWORD)

    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_write_secret_rejects_short_password(tmp_path) -> None:
    with pytest.raises(ValueError, match="12 caracteres"):
        write_secret(tmp_path / "secrets.toml", "corta")
    assert not (tmp_path / "secrets.toml").exists()


def test_local_config_binds_only_to_loopback() -> None:
    root = Path(__file__).parents[1]
    config = tomllib.loads((root / ".streamlit" / "config.toml").read_text("utf-8"))

    assert config["server"]["address"] == "127.0.0.1"
    assert "--server.address 127.0.0.1" in (root / "run_windows.bat").read_text(
        "utf-8"
    )
    example = tomllib.loads(
        (root / ".streamlit" / "secrets.example.toml").read_text("utf-8")
    )
    assert not example["auth"]["password_hash"].startswith("scrypt$")
