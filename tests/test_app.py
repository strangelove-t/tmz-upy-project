from app_helpers import ROOT, TEST_PASSWORD, configured_app, log_in
from streamlit.testing.v1 import AppTest


def test_app_requires_password() -> None:
    app = configured_app().run()

    assert not app.exception
    assert any(field.label == "Contraseña" for field in app.text_input)
    assert not app.get("file_uploader")


def test_app_without_configured_password_is_blocked() -> None:
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    # Secretos explícitos sin [auth]: no depende del secrets.toml local.
    app.secrets["otro"] = {}
    app.run()

    assert not app.exception
    assert any("contraseña local configurada" in error.value for error in app.error)
    assert not app.text_input
    assert not app.get("file_uploader")


def test_app_rejects_wrong_password_and_accepts_correct_one() -> None:
    app = log_in(configured_app().run(), "incorrecta-pero-larga")

    assert any("Contraseña incorrecta" in error.value for error in app.error)
    assert not app.get("file_uploader")

    log_in(app, TEST_PASSWORD)

    assert not app.exception
    assert app.session_state["authenticated"] is True
    assert len(app.get("file_uploader")) == 1


def test_logout_clears_session() -> None:
    app = configured_app(authenticated=True).run()

    next(button for button in app.button if button.label == "Cerrar sesión").click()
    app.run()

    assert "authenticated" not in app.session_state
    assert any(field.label == "Contraseña" for field in app.text_input)


def test_app_shows_csv_import_control() -> None:
    app = configured_app(authenticated=True).run()

    assert not app.exception
    assert len(app.get("file_uploader")) == 1
    assert any(
        "Catálogo aprobado: 105" in caption.value
        and "Texto verificado: 0" in caption.value
        and "Pendientes de revisión: 0" in caption.value
        for caption in app.caption
    )
    assert any(
        "Las líneas 2–15 se excluyen de la importación real" in info.value
        for info in app.info
    )
    assert any("Scoring activo: 0.2" in caption.value for caption in app.caption)
