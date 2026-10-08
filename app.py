import sqlite3
from pathlib import Path

import streamlit as st

from tamizaje import SCORING_VERSION
from tamizaje.alerts import AlertConfigError
from tamizaje.database import (
    DuplicateImportError,
    InvalidPreviewError,
    connect_database,
    import_preview,
    initialize_database,
    is_imported,
    recalculate_all,
)
from tamizaje.importers import ImportErrorSafe, preview_csv
from tamizaje.models import EngineConfigError, load_engine_config
from tamizaje.questionnaire import (
    QuestionnaireCatalogError,
    load_questionnaire,
    load_questionnaire_aliases,
)
from tamizaje.questionnaire_draft import read_pending_headers
from tamizaje.recommendations import RecommendationConfigError
from tamizaje.scoring_config import ScoringConfigError
from tamizaje.ui import require_authentication

TEST_DATA_ROWS = 14

st.set_page_config(page_title="Tamizaje UPY", page_icon="🎓", layout="wide")
require_authentication()

st.title("Tamizaje y Orientación UPY")
st.caption(f"Aplicación local · scoring v{SCORING_VERSION}")
st.info(
    "Importa la exportación de Forms y consulta Resumen, Casos, Grupos, "
    "Estudiantes y Reportes en el menú lateral. Las líneas 2–15 se excluyen de "
    "la importación real."
)
st.warning(
    "Este instrumento es de tamizaje y orientación; no constituye un "
    "diagnóstico psicológico o clínico."
)

st.header("Importar respuestas")
try:
    questionnaire = load_questionnaire(Path("config/questionnaire.csv"))
    aliases = load_questionnaire_aliases(
        Path("config/questionnaire_aliases.csv"), questionnaire
    )
    pending_headers = read_pending_headers(Path("config/questionnaire_draft.csv"))
    engine = load_engine_config(Path("config"))
except (
    AlertConfigError,
    EngineConfigError,
    QuestionnaireCatalogError,
    RecommendationConfigError,
    ScoringConfigError,
    ImportErrorSafe,
    OSError,
):
    questionnaire = ()
    aliases = ()
    pending_headers = ()
    engine = None
    st.error("No fue posible cargar la configuración del cuestionario y scoring.")

approved_catalog_count = sum(
    question.mapping_status == "approved" for question in questionnaire
)
verified_catalog_count = sum(
    question.mapping_status == "verified_text" for question in questionnaire
)
st.caption(
    f"Catálogo aprobado: {approved_catalog_count} · "
    f"Texto verificado: {verified_catalog_count} · "
    f"Pendientes de revisión: {len(pending_headers)}"
)
if engine is not None:
    st.caption(
        f"Scoring activo: {engine.scoring.version} · "
        f"Reglas de alerta: {engine.alerts.version} "
        f"({len(engine.alerts.rules)} reglas)"
    )
uploaded_file = st.file_uploader("Selecciona una exportación CSV", type=["csv"])
test_mode = st.toggle(
    "Modo seguro: analizar sólo los 14 registros de prueba",
    value=True,
    help="En el archivo actual corresponden a las líneas 2–15.",
)

if uploaded_file is not None:
    content = uploaded_file.getvalue()
    try:
        preview = preview_csv(
            uploaded_file.name,
            content,
            max_rows=TEST_DATA_ROWS if test_mode else None,
            skip_rows=0 if test_mode else TEST_DATA_ROWS,
            questionnaire=questionnaire,
            pending_headers=pending_headers,
            aliases=aliases,
        )
    except ImportErrorSafe:
        st.error("No fue posible interpretar la estructura del CSV.")
    else:
        summary = preview.summary()
        metadata_columns = st.columns(4)
        metadata_columns[0].metric("Registros analizados", preview.row_count)
        metadata_columns[1].metric("Columnas", preview.column_count)
        metadata_columns[2].metric("Codificación", preview.encoding)
        metadata_columns[3].metric("Hash", summary["sha256_short"])

        delimiter_names = {";": "punto y coma", ",": "coma", "\t": "tabulador"}
        st.caption(
            f"Separador: {delimiter_names.get(preview.delimiter, 'otro permitido')}"
        )

        for issue in preview.validation.errors:
            location = f" Fila {issue.row_number}." if issue.row_number else ""
            st.error(f"{issue.message}{location}")
        for issue in preview.validation.warnings:
            st.warning(issue.message)

        mapping = preview.mapping
        if mapping is not None:
            mapping_columns = st.columns(5)
            mapping_columns[0].metric("Aprobadas", mapping.approved_count)
            mapping_columns[1].metric("Texto verificado", mapping.verified_count)
            mapping_columns[2].metric("Pendientes", len(mapping.pending_indices))
            mapping_columns[3].metric("Desconocidas", len(mapping.unknown_indices))
            mapping_columns[4].metric("Ambiguas", len(mapping.ambiguous_indices))
            if not mapping.is_valid:
                st.error(
                    "El mapeo del cuestionario está incompleto; la importación "
                    "permanece bloqueada."
                )

        if test_mode:
            st.info(
                "Modo seguro activo: esta previsualización no puede guardarse "
                "en la base de datos."
            )
        else:
            st.warning(
                "El archivo completo incluye información real, sensible y "
                "confidencial desde la línea 16."
            )
            authorized = st.checkbox(
                "Confirmo que tengo autorización para procesar estos datos reales."
            )
            connection = connect_database(Path("data") / "tamizaje.db")
            initialize_database(connection)
            duplicate = is_imported(connection, preview.sha256)

            if duplicate:
                st.error("Este archivo ya fue importado y no puede duplicarse.")

            if st.button(
                "Confirmar importación",
                type="primary",
                disabled=(
                    not authorized
                    or not preview.validation.is_valid
                    or mapping is None
                    or not mapping.is_valid
                    or engine is None
                    or duplicate
                ),
            ):
                try:
                    import_id = import_preview(
                        connection,
                        preview,
                        questionnaire,
                        engine.scoring,
                        alert_config=engine.alerts,
                        recommendations=engine.recommendations,
                    )
                except (DuplicateImportError, InvalidPreviewError, sqlite3.Error):
                    st.error(
                        "La importación no pudo completarse y no se guardaron "
                        "cambios parciales."
                    )
                else:
                    st.success(f"Importación completada con folio local {import_id}.")
            connection.close()

DATABASE_PATH = Path("data") / "tamizaje.db"
if engine is not None and DATABASE_PATH.exists():
    st.header("Recalcular envíos históricos")
    st.write(
        "Aplica las versiones activas de scoring y reglas de alerta a todos los "
        "envíos guardados, sin reimportar el archivo. Los resultados de otras "
        "versiones se conservan y el seguimiento de los casos no se modifica."
    )
    confirm_recalculation = st.checkbox(
        f"Confirmo recalcular con scoring {engine.scoring.version} y reglas "
        f"{engine.alerts.version}."
    )
    if st.button("Recalcular", disabled=not confirm_recalculation):
        connection = connect_database(DATABASE_PATH)
        initialize_database(connection)
        try:
            count = recalculate_all(
                connection, engine.scoring, engine.alerts, engine.recommendations
            )
        except sqlite3.Error:
            st.error("El recálculo falló y no se guardaron cambios parciales.")
        else:
            st.success(f"Se recalcularon {count} envíos.")
        finally:
            connection.close()
