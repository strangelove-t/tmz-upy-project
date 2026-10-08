from datetime import datetime
from pathlib import Path

import streamlit as st

from tamizaje.database import connect_database, record_export
from tamizaje.reports import (
    ReportError,
    build_report_data,
    export_batch,
    generate_report,
    load_template,
)
from tamizaje.repository import students_frame
from tamizaje.ui import DATABASE_PATH, EXPORTS_DIR, require_context

st.title("Reportes")
st.caption(
    "Los reportes usan una lista blanca de campos: el del estudiante no incluye "
    "alertas ni notas internas y el del asesor excluye información de salud, "
    "respuestas abiertas y alertas."
)

engine, connection = require_context()
students = students_frame(connection)
students = students[students["is_current"] == 1]
if students.empty:
    st.info("Aún no hay envíos procesados.")
    connection.close()
    st.stop()

REPORT_LABELS = {
    "student": "Reporte del estudiante",
    "advisor": "Expediente para asesor",
}


def log_download(submission_id: int, report_type: str, filename: str) -> None:
    log_connection = connect_database(DATABASE_PATH)
    record_export(
        log_connection,
        submission_id,
        report_type,
        f"descarga:{filename}",
        load_template(report_type).template_version,
    )
    log_connection.close()


st.header("Reporte individual")
labels = {
    int(row.submission_id): f"{row.student_name} · {row.career} · {row.group_name}"
    for row in students.itertuples()
}
submission_id = st.selectbox("Estudiante", list(labels), format_func=labels.get)
report_type = st.radio(
    "Tipo de reporte",
    list(REPORT_LABELS),
    format_func=REPORT_LABELS.get,
    horizontal=True,
)

try:
    template = load_template(report_type)
    data = build_report_data(connection, submission_id, engine, template)
    filename, content = generate_report(connection, submission_id, engine, report_type)
except ReportError as error:
    st.error(f"No fue posible generar el reporte: {error}")
else:
    with st.container(border=True):
        st.subheader(f"Vista previa · {template.title}")
        for field in ("student_name", "career", "group_name", "generated_at"):
            if field in data:
                st.write(data[field])
        st.table(
            [
                {
                    "Área": line.area_name,
                    "Puntaje": f"{line.score:.1f}" if line.score is not None else "—",
                    "Semáforo": line.traffic_light or "Pendiente de revisión",
                }
                for line in data["areas"]
            ]
        )
        for area_name, text in data.get("recommendations", []):
            st.markdown(f"**{area_name}:** {text}")
        st.caption(template.disclaimer)
    st.download_button(
        f"Descargar {REPORT_LABELS[report_type].lower()}",
        content,
        file_name=filename,
        mime="application/pdf",
        on_click=log_download,
        args=(submission_id, report_type, filename),
        type="primary",
    )

st.header("Generación por lote")
st.write(
    f"Genera ambos reportes para {len(students)} envíos vigentes en la carpeta "
    "local `exports/` y un manifiesto correo → archivo."
)
if st.button("Generar todos los reportes"):
    output_dir = EXPORTS_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
    with st.spinner("Generando reportes…"):
        manifest = export_batch(connection, engine, output_dir)
    st.session_state["manifest"] = str(manifest)
    st.success(f"Reportes generados en {output_dir}")
if "manifest" in st.session_state:
    manifest_path = Path(st.session_state["manifest"])
    if manifest_path.exists():
        st.download_button(
            "Descargar manifiesto",
            manifest_path.read_bytes(),
            file_name="manifiesto.csv",
            mime="text/csv",
        )
connection.close()
