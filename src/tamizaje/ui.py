"""Utilidades compartidas por las páginas de Streamlit."""

import sqlite3
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
DISCLAIMER = (
    "Este instrumento es de tamizaje y orientación; no constituye un "
    "diagnóstico psicológico o clínico."
)


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


def require_authentication(*, show_logout: bool = True) -> None:
    """Detiene la ejecución hasta validar la contraseña local única."""
    if st.session_state.get("authenticated"):
        if show_logout and st.sidebar.button("Cerrar sesión", key="logout"):
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
    require_authentication()
    engine = load_engine()
    if engine is None:
        st.error("No fue posible cargar la configuración del motor.")
        st.stop()
    if not DATABASE_PATH.exists():
        st.info("Aún no hay datos. Importa una exportación desde la página principal.")
        st.stop()
    connection = connect_database(DATABASE_PATH)
    initialize_database(connection)
    return engine, connection


def area_names(engine: EngineConfig) -> dict[str, str]:
    return {area.area_code: area.area_name for area in engine.scoring.areas}
