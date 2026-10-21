import sqlite3
from datetime import datetime

import streamlit as st

from tamizaje import ui
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
from tamizaje.repository import last_import
from tamizaje.scoring_config import ScoringConfigError
from tamizaje.ui import DISCLAIMER, page_header, require_authentication

REAL_IMPORT_PHRASE = "IMPORTAR"

require_authentication(show_logout=False)
page_header(
    "Administración",
    "Importación de respuestas y recálculo. Úsala sólo al recibir una "
    "exportación nueva o al cambiar de versión.",
)

try:
    questionnaire = load_questionnaire(ui.CONFIG_DIR / "questionnaire.csv")
    aliases = load_questionnaire_aliases(
        ui.CONFIG_DIR / "questionnaire_aliases.csv", questionnaire
    )
    pending_headers = read_pending_headers(ui.CONFIG_DIR / "questionnaire_draft.csv")
    engine = load_engine_config(ui.CONFIG_DIR)
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
    st.error(
        "No fue posible cargar la configuración del cuestionario y scoring. "
        "La importación está bloqueada; contacta a soporte."
    )

latest = None
if ui.DATABASE_PATH.exists():
    status_connection = connect_database(ui.DATABASE_PATH)
    initialize_database(status_connection)
    latest = last_import(status_connection)
    status_connection.close()

status = st.columns(3)
if latest is None:
    status[0].metric("Última importación", "Ninguna")
else:
    imported_at = datetime.fromisoformat(latest["imported_at"])
    if engine is not None:
        imported_at = imported_at.astimezone(engine.report_timezone)
    status[0].metric("Última importación", f"{imported_at:%d/%m/%Y %H:%M}")
status[1].metric("Scoring", f"v{engine.scoring.version}" if engine else "—")
status[2].metric(
    "Reglas de alerta",
    f"v{engine.alerts.version}" if engine else "—",
    help=f"{len(engine.alerts.rules)} reglas activas." if engine else None,
)
st.caption(
    f"Catálogo aprobado: {sum(q.mapping_status == 'approved' for q in questionnaire)}"
    f" · Texto verificado: "
    f"{sum(q.mapping_status == 'verified_text' for q in questionnaire)}"
    f" · Pendientes de revisión: {len(pending_headers)}"
    + (
        f" · Scoring activo: {engine.scoring.version}"
        f" · Reglas de alerta: {engine.alerts.version}"
        if engine
        else ""
    )
)

st.header("Importar respuestas")

st.subheader("1. Archivo")
uploaded_file = st.file_uploader("Exportación CSV de Microsoft Forms", type=["csv"])
st.info(
    "Se analizarán todas las respuestas desde la línea 2. La validación no "
    "guarda datos; para importarlos se requiere autorización escrita y "
    "confirmación expresa."
)

st.subheader("2. Validación")
if uploaded_file is None:
    st.caption("Selecciona un archivo para validarlo.")
    preview = None
else:
    try:
        preview = preview_csv(
            uploaded_file.name,
            uploaded_file.getvalue(),
            questionnaire=questionnaire,
            pending_headers=pending_headers,
            aliases=aliases,
        )
    except ImportErrorSafe:
        preview = None
        st.error(
            "No fue posible leer la estructura del CSV. Verifica que sea la "
            "exportación original de Forms."
        )

mapping = preview.mapping if preview is not None else None
ready = (
    preview is not None
    and preview.validation.is_valid
    and mapping is not None
    and mapping.is_valid
    and engine is not None
)
if preview is not None:
    for issue in preview.validation.errors:
        location = f" Fila {issue.row_number}." if issue.row_number else ""
        st.error(f"{issue.message}{location}")
    for issue in preview.validation.warnings:
        st.warning(issue.message)
    if mapping is not None and not mapping.is_valid:
        st.error(
            "Algunas columnas no coinciden con el cuestionario "
            f"({len(mapping.unknown_indices)} desconocidas, "
            f"{len(mapping.ambiguous_indices)} ambiguas, "
            f"{len(mapping.pending_indices) + mapping.verified_count} pendientes). "
            "La importación queda bloqueada."
        )
    elif ready:
        st.success("Estructura y columnas válidas.")

    st.subheader("3. Resumen")
    summary = preview.summary()
    columns = st.columns(3)
    columns[0].metric("Registros analizados", preview.row_count)
    columns[1].metric("Columnas", preview.column_count)
    columns[2].metric(
        "Columnas reconocidas", mapping.approved_count if mapping else "—"
    )
    delimiter_names = {";": "punto y coma", ",": "coma", "\t": "tabulador"}
    first_line = preview.source_row_numbers[0] if preview.source_row_numbers else "—"
    last_line = preview.source_row_numbers[-1] if preview.source_row_numbers else "—"
    st.caption(
        f"Líneas {first_line}–{last_line} · codificación {preview.encoding} · "
        f"separador {delimiter_names.get(preview.delimiter, 'otro permitido')} · "
        f"huella {summary['sha256_short']}"
    )

    st.subheader("4. Confirmación")
    if not ready:
        st.warning("Corrige los problemas de validación antes de importar.")
    else:
        connection = connect_database(ui.DATABASE_PATH)
        initialize_database(connection)
        if is_imported(connection, preview.sha256):
            st.error("Este archivo ya fue importado y no puede duplicarse.")
        else:
            authorized = st.checkbox(
                "Confirmo que la maestra autorizó por escrito procesar estos "
                "datos reales."
            )
            phrase = st.text_input(
                f"Escribe {REAL_IMPORT_PHRASE} para confirmar",
                disabled=not authorized,
            )
            if st.button(
                f"Importar {preview.row_count} registros reales",
                type="primary",
                disabled=not authorized or phrase.strip() != REAL_IMPORT_PHRASE,
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
                    st.success(
                        f"Importación completada (folio local {import_id}). "
                        "Revisa los pendientes en Inicio."
                    )
        connection.close()

st.divider()
with st.expander("Recalcular resultados"):
    st.write(
        "Aplica las versiones activas de scoring y reglas de alerta a todos los "
        "envíos guardados, sin reimportar el archivo. Los resultados de otras "
        "versiones se conservan y el seguimiento de los casos no se modifica."
    )
    if engine is None:
        st.warning("La configuración no cargó; el recálculo está bloqueado.")
    elif not ui.DATABASE_PATH.exists():
        st.caption("No hay envíos guardados para recalcular.")
    else:
        confirm_recalculation = st.checkbox(
            f"Confirmo recalcular con scoring {engine.scoring.version} y reglas "
            f"{engine.alerts.version}."
        )
        if st.button("Recalcular", disabled=not confirm_recalculation):
            connection = connect_database(ui.DATABASE_PATH)
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

st.caption(DISCLAIMER)
