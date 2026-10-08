"""Utilidades compartidas por las páginas de Streamlit."""

import sqlite3
from pathlib import Path

import streamlit as st

from tamizaje.alerts import AlertConfigError
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


def require_context() -> tuple[EngineConfig, sqlite3.Connection]:
    """Detiene la página si falta configuración o no hay importaciones."""
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
