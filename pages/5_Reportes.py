from datetime import datetime
from pathlib import Path

import streamlit as st

from tamizaje import ui
from tamizaje.database import connect_database, record_export
from tamizaje.reports import (
    ReportError,
    build_report_data,
    export_batch,
    generate_report,
    load_template,
)
from tamizaje.repository import students_frame
from tamizaje.ui import NO_SUBMISSIONS, page_header, require_context

page_header(
    "Reportes",
    "Sólo incluyen campos autorizados: el del alumno no lleva alertas ni notas "
    "internas; el del asesor excluye salud, respuestas abiertas y alertas.",
)

engine, connection = require_context()
students = students_frame(connection)
students = students[students["is_current"] == 1]
if students.empty:
    st.info(NO_SUBMISSIONS)
    connection.close()
    st.stop()

REPORT_LABELS = {
    "student": "Reporte del alumno",
    "advisor": "Expediente para asesor",
}


def log_download(submission_id: int, report_type: str, filename: str) -> None:
    log_connection = connect_database(ui.DATABASE_PATH)
    record_export(
        log_connection,
        submission_id,
        report_type,
        f"descarga:{filename}",
        load_template(report_type).template_version,
    )
    log_connection.close()


individual_tab, batch_tab = st.tabs(["Individual", "Por lote"])

with individual_tab:
    labels = {
        int(row.submission_id): (
            f"{row.student_name} · {row.career} · {row.group_name}"
        )
        for row in students.itertuples()
    }
    ids = list(labels)
    # Llegada desde el expediente: preselecciona al mismo alumno.
    target = st.session_state.pop("reports_target", None)
    columns = st.columns([2, 1])
    submission_id = columns[0].selectbox(
        "Estudiante",
        ids,
        index=ids.index(target) if target in ids else 0,
        format_func=labels.get,
    )
    report_type = columns[1].radio(
        "Tipo de reporte",
        list(REPORT_LABELS),
        format_func=REPORT_LABELS.get,
    )

    try:
        template = load_template(report_type)
        data = build_report_data(connection, submission_id, engine, template)
        filename, content = generate_report(
            connection, submission_id, engine, report_type
        )
    except ReportError as error:
        st.error(f"No fue posible generar el reporte: {error}")
    else:
        with st.container(border=True):
            st.subheader(f"Vista previa · {template.title}")
            st.caption(
                " · ".join(
                    str(data[field])
                    for field in ("student_name", "career", "group_name")
                    if field in data
                )
            )
            st.dataframe(
                [
                    {
                        "Área": line.area_name,
                        "Puntaje": (
                            f"{line.score:.1f}" if line.score is not None else "—"
                        ),
                        "Semáforo": line.traffic_light or "Pendiente de revisión",
                    }
                    for line in data["areas"]
                ],
                hide_index=True,
                width="stretch",
            )
            for area_name, text in data.get("recommendations", []):
                st.markdown(f"**{area_name}:** {text}")
            st.caption(template.disclaimer)
        st.download_button(
            f"Descargar {REPORT_LABELS[report_type].lower()} (PDF)",
            content,
            file_name=filename,
            mime="application/pdf",
            on_click=log_download,
            args=(submission_id, report_type, filename),
            type="primary",
            icon=":material/download:",
        )

with batch_tab:
    st.warning(
        "Los reportes por lote contienen información confidencial de todos los "
        "alumnos. Se guardan sólo en esta computadora; entrégalos únicamente por "
        "canales institucionales autorizados."
    )
    st.write(
        f"Genera el reporte del alumno y el expediente para asesor de "
        f"{len(students)} alumnos, más una lista de qué archivo corresponde a "
        "cada correo."
    )
    confirm = st.checkbox("Entiendo que los archivos generados son confidenciales.")
    if st.button("Generar todos los reportes", disabled=not confirm):
        output_dir = ui.EXPORTS_DIR / datetime.now(engine.report_timezone).strftime(
            "%Y%m%d-%H%M%S"
        )
        with st.spinner("Generando reportes…"):
            manifest = export_batch(connection, engine, output_dir)
        st.session_state["manifest"] = str(manifest)
    if "manifest" in st.session_state:
        manifest_path = Path(st.session_state["manifest"])
        if manifest_path.exists():
            pdf_count = len(list(manifest_path.parent.glob("*.pdf")))
            st.success(
                f"Se generaron {pdf_count} PDF y el manifiesto en la carpeta local "
                f"{manifest_path.parent}"
            )
            st.download_button(
                "Descargar manifiesto",
                manifest_path.read_bytes(),
                file_name="manifiesto.csv",
                mime="text/csv",
            )
connection.close()
