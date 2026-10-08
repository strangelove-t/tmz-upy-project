import pytest

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
