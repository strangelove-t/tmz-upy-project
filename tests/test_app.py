from app_helpers import (
    ROOT,
    TEST_PASSWORD,
    configured_app,
    log_in,
    run_authenticated_page,
)
from streamlit.testing.v1 import AppTest

from tamizaje import ui


def test_app_requires_password() -> None:
    app = configured_app().run()

    assert not app.exception
    assert any(field.label == "Contraseña" for field in app.text_input)
    assert not app.get("file_uploader")
    assert not app.metric


def test_app_without_configured_password_is_blocked() -> None:
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    # Secretos explícitos sin [auth]: no depende del secrets.toml local.
    app.secrets["otro"] = {}
    app.run()

    assert not app.exception
    assert any("contraseña local configurada" in error.value for error in app.error)
    assert not app.text_input


def test_app_rejects_wrong_password_and_accepts_correct_one() -> None:
    app = log_in(configured_app().run(), "incorrecta-pero-larga")

    assert any("Contraseña incorrecta" in error.value for error in app.error)
    assert "authenticated" not in app.session_state

    log_in(app, TEST_PASSWORD)

    assert not app.exception
    assert app.session_state["authenticated"] is True
    assert app.title[0].value == "Inicio"


def test_logout_clears_session() -> None:
    app = configured_app(authenticated=True).run()

    next(button for button in app.button if button.label == "Cerrar sesión").click()
    app.run()

    assert "authenticated" not in app.session_state
    assert any(field.label == "Contraseña" for field in app.text_input)


def test_authenticated_app_opens_operational_home() -> None:
    app = configured_app(authenticated=True).run()

    assert not app.exception
    assert app.title[0].value == "Inicio"
    assert not app.get("file_uploader")


def test_navigation_is_ordered_by_daily_use() -> None:
    assert [page.title for page in ui.NAVIGATION] == [
        "Inicio",
        "Casos",
        "Condiciones declaradas",
        "Estudiantes",
        "Grupos",
        "Reportes",
        "Administración",
    ]
    assert all((ROOT / page.path).is_file() for page in ui.NAVIGATION)


def test_administration_keeps_csv_import_control() -> None:
    app = run_authenticated_page("6_Administracion.py")

    assert not app.exception
    assert app.title[0].value == "Administración"
    assert len(app.get("file_uploader")) == 1
    assert any(
        "Catálogo aprobado: 106" in caption.value
        and "Texto verificado: 0" in caption.value
        and "Pendientes de revisión: 0" in caption.value
        for caption in app.caption
    )
    assert any("Scoring activo: 0.2" in caption.value for caption in app.caption)


def test_exit_button_closes_session_and_schedules_shutdown(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(ui, "_schedule_termination", lambda: calls.append(True))
    app = configured_app(authenticated=True).run()

    next(b for b in app.button if b.label == "Salir de la aplicación").click().run()

    assert calls == [True]
    assert "authenticated" not in app.session_state
    assert any("ya puedes cerrar" in item.value.lower() for item in app.success)


def test_windows_launcher_opens_browser_on_loopback() -> None:
    launcher = (ROOT / "run_windows.bat").read_text("utf-8")

    assert "--server.address 127.0.0.1" in launcher
    assert "--server.headless false" in launcher


def test_windows_desktop_launcher_uses_cmd_without_powershell() -> None:
    launcher = (ROOT / "abrir_Tamizaje.bat").read_text("utf-8")

    assert 'cd /d "%~dp0"' in launcher
    assert 'if not exist ".venv\\Scripts\\python.exe" (' in launcher
    assert 'call ".venv\\Scripts\\activate.bat"' in launcher
    assert 'call ".\\run_windows.bat"' in launcher
    assert "Activate.ps1" not in launcher


def test_theme_uses_larger_base_font() -> None:
    import tomllib

    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text("utf-8"))

    assert config["theme"]["baseFontSize"] >= 17


def test_charts_are_rendered_through_shared_helper() -> None:
    for page in (ROOT / "pages").glob("*.py"):
        assert "st.plotly_chart" not in page.read_text("utf-8"), page.name
