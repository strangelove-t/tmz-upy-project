import sqlite3
from pathlib import Path

import streamlit as st

from tamizaje import SCORING_VERSION
from tamizaje.database import (
    DuplicateImportError,
    InvalidPreviewError,
    connect_database,
    import_preview,
    initialize_database,
    is_imported,
)
from tamizaje.importers import ImportErrorSafe, preview_csv
from tamizaje.questionnaire import (
    QuestionnaireCatalogError,
    load_questionnaire,
    load_questionnaire_aliases,
)
from tamizaje.questionnaire_draft import read_pending_headers
from tamizaje.scoring_config import ScoringConfigError, load_scoring_config

TEST_DATA_ROWS = 14

st.set_page_config(page_title="Tamizaje UPY", page_icon="🎓", layout="wide")

st.title("Tamizaje y Orientación UPY")
st.caption(f"Aplicación local · scoring v{SCORING_VERSION}")
st.info(
    "El diccionario y la persistencia separada están listos. Las líneas 2–15 "
    "se excluyen de la importación real."
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
    scoring_config = load_scoring_config(Path("config"))
except (QuestionnaireCatalogError, ScoringConfigError, ImportErrorSafe, OSError):
    questionnaire = ()
    aliases = ()
    pending_headers = ()
    scoring_config = None
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
if scoring_config is not None:
    st.caption(f"Scoring activo: {scoring_config.version}")
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
                    or scoring_config is None
                    or duplicate
                ),
            ):
                try:
                    import_id = import_preview(
                        connection,
                        preview,
                        questionnaire,
                        scoring_config,
                    )
                except (DuplicateImportError, InvalidPreviewError, sqlite3.Error):
                    st.error(
                        "La importación no pudo completarse y no se guardaron "
                        "cambios parciales."
                    )
                else:
                    st.success(f"Importación completada con folio local {import_id}.")
            connection.close()
