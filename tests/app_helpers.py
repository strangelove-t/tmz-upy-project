"""Ayudas de AppTest con una contraseña sintética."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from tamizaje.auth import hash_password

ROOT = Path(__file__).parents[1]
TEST_PASSWORD = "contraseña-sintética-de-prueba"
TEST_HASH = hash_password(TEST_PASSWORD, salt=bytes(16))


def configured_app(path: str = "app.py", *, authenticated: bool = False) -> AppTest:
    app = AppTest.from_file(str(ROOT / path), default_timeout=30)
    app.secrets["auth"] = {"password_hash": TEST_HASH}
    if authenticated:
        app.session_state["authenticated"] = True
    return app


def run_authenticated_page(name: str) -> AppTest:
    """Ejecuta una página a través del router, como en la aplicación real."""
    app = configured_app(authenticated=True)
    app.switch_page(f"pages/{name}")
    return app.run()


def log_in(app: AppTest, password: str) -> AppTest:
    next(field for field in app.text_input if field.label == "Contraseña").input(
        password
    )
    next(button for button in app.button if button.label == "Entrar").click()
    return app.run()
