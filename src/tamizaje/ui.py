"""Utilidades compartidas por las páginas de Streamlit."""

import os
import signal
import sqlite3
import threading
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import streamlit as st

from tamizaje.alerts import AlertConfigError
from tamizaje.auth import verify_password
from tamizaje.database import connect_database, initialize_database
from tamizaje.models import EngineConfig, EngineConfigError, load_engine_config
from tamizaje.questionnaire import QuestionnaireCatalogError, load_questionnaire
from tamizaje.recommendations import RecommendationConfigError
from tamizaje.scoring_config import ScoringConfigError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
DATABASE_PATH = PROJECT_ROOT / "data" / "tamizaje.db"
EXPORTS_DIR = PROJECT_ROOT / "exports"
LIGHT_COLORS = {
    "Verde": "#2e7d32",
    "Amarillo": "#f9a825",
    "Rojo": "#c62828",
    "Incompleta": "#9e9e9e",
}
LIGHT_ORDER = ["Verde", "Amarillo", "Rojo", "Incompleta"]
NO_SUBMISSIONS = (
    "Aún no hay respuestas cargadas. Se importan desde Administración."
)
DISCLAIMER = (
    "Este instrumento es de tamizaje y orientación; no constituye un "
    "diagnóstico psicológico o clínico."
)




@dataclass(frozen=True)
class NavigationPage:
    path: str
    title: str
    icon: str


# Ordenado por frecuencia de uso; Administración queda fuera del día a día.
NAVIGATION = (
    NavigationPage("pages/1_Resumen.py", "Inicio", ":material/home:"),
    NavigationPage("pages/2_Casos.py", "Casos", ":material/assignment:"),
    NavigationPage("pages/4_Estudiantes.py", "Estudiantes", ":material/school:"),
    NavigationPage("pages/3_Grupos.py", "Grupos", ":material/groups:"),
    NavigationPage("pages/5_Reportes.py", "Reportes", ":material/description:"),
    NavigationPage(
        "pages/6_Administracion.py", "Administración", ":material/settings:"
    ),
)


def apply_theme() -> None:
    """CSS mínimo compartido; los colores base viven en .streamlit/config.toml."""
    st.markdown(
        """
        <style>
        .block-container {max-width: 1180px; padding-top: 2rem;}
        [data-testid="stMetric"] {
            background: #ffffff; border: 1px solid #dfe5ea;
            border-radius: 12px; padding: 0.75rem 1rem;
        }
        div[data-testid="stForm"] {
            border: 1px solid #dfe5ea; border-radius: 12px; padding: 1rem;
        }
        [data-testid="stCaptionContainer"] {color: #4a5560 !important;}
        a:focus-visible, button:focus-visible, [role="tab"]:focus-visible,
        input:focus-visible, textarea:focus-visible, summary:focus-visible {
            outline: 3px solid #0b6e75 !important; outline-offset: 2px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_date(value: str | None, timezone=None) -> str:
    """Fecha ISO (o fecha-hora UTC) en formato dd/mm/aaaa; vacío como "—"."""
    if not value:
        return "—"
    try:
        if len(value) <= 10:
            return date.fromisoformat(value).strftime("%d/%m/%Y")
        moment = datetime.fromisoformat(value)
        if timezone is not None and moment.tzinfo is not None:
            moment = moment.astimezone(timezone)
        return moment.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value


def yes_no(value: object) -> str:
    return "Sí" if bool(value) else "No"


def status_row(items: dict[str, str]) -> None:
    """Etiqueta + valor en texto completo; st.metric recorta valores largos."""
    for column, (label, value) in zip(
        st.columns(len(items)), items.items(), strict=True
    ):
        column.caption(label)
        column.markdown(f"**{value}**")


def page_header(title: str, description: str) -> None:
    st.title(title)
    st.caption(description)


@st.cache_resource
def load_engine() -> EngineConfig | None:
    try:
        return load_engine_config(CONFIG_DIR)
    except (
        AlertConfigError,
        EngineConfigError,
        QuestionnaireCatalogError,
        RecommendationConfigError,
        ScoringConfigError,
        OSError,
    ):
        return None


@st.cache_resource
def question_texts() -> dict[str, str]:
    return {
        question.question_code: question.question_text
        for question in load_questionnaire(CONFIG_DIR / "questionnaire.csv")
        if question.question_code is not None
    }


def _configured_password_hash() -> str | None:
    try:
        return str(st.secrets["auth"]["password_hash"])
    except (KeyError, FileNotFoundError, TypeError):
        return None


SHUTDOWN_DELAY_SECONDS = 2.0


def _schedule_termination() -> None:
    """Apaga el servidor local tras mostrar el mensaje de despedida."""
    timer = threading.Timer(
        SHUTDOWN_DELAY_SECONDS, lambda: os.kill(os.getpid(), signal.SIGTERM)
    )
    timer.daemon = True
    timer.start()


def shutdown_application() -> None:
    """Cierra la sesión y detiene la aplicación (uso local de una sola persona)."""
    st.session_state.clear()
    _schedule_termination()
    st.success(
        "La aplicación se cerró correctamente. Ya puedes cerrar esta pestaña del "
        "navegador. Si aparece un aviso de conexión, es normal."
    )
    st.stop()


def require_authentication(*, show_logout: bool = True) -> None:
    """Detiene la ejecución hasta validar la contraseña local única."""
    if st.session_state.get("authenticated"):
        if show_logout:
            if st.sidebar.button(
                "Salir de la aplicación",
                key="exit_app",
                type="primary",
                icon=":material/power_settings_new:",
                help="Cierra la sesión y apaga la aplicación en esta computadora.",
            ):
                shutdown_application()
            if st.sidebar.button("Cerrar sesión", key="logout"):
                st.session_state.clear()
                st.rerun()
        return

    password_hash = _configured_password_hash()
    if password_hash is None:
        st.error(
            "La aplicación no tiene una contraseña local configurada. Ejecuta "
            "scripts/set_local_password.py en esta computadora."
        )
        st.stop()

    st.title("Tamizaje y Orientación UPY")
    with st.form("login"):
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Entrar", type="primary")
    if submitted and verify_password(password, password_hash):
        st.session_state["authenticated"] = True
        st.rerun()
    if submitted:
        st.error("Contraseña incorrecta.")
    st.stop()


def require_context() -> tuple[EngineConfig, sqlite3.Connection]:
    """Detiene la página sin sesión, sin configuración o sin importaciones."""
    require_authentication(show_logout=False)
    engine = load_engine()
    if engine is None:
        st.error("No fue posible cargar la configuración del motor.")
        st.stop()
    if not DATABASE_PATH.exists():
        st.info("Aún no hay datos. Importa una exportación desde Administración.")
        st.stop()
    connection = connect_database(DATABASE_PATH)
    initialize_database(connection)
    return engine, connection


def area_names(engine: EngineConfig) -> dict[str, str]:
    return {area.area_code: area.area_name for area in engine.scoring.areas}
