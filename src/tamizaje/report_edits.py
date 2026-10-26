"""Textos editables y notas de los reportes, guardados por alumno o grupo.

Sólo se editan textos explicativos: cifras, semáforos y nombres vienen del
cuestionario y nunca se modifican aquí. En la base se guarda únicamente lo que
difiere del texto original, así que restaurar equivale a borrar la edición.
"""

import sqlite3
from dataclasses import dataclass, replace
from datetime import UTC, datetime

MAX_TEXT_LENGTH = 2000
REPORT_TYPES = ("student", "tutor", "group")
DEFAULT_GROUP_INTRODUCTION = (
    "Este informe resume las respuestas del grupo para orientar conversaciones "
    "y apoyos. No califica a cada alumno ni constituye un diagnóstico."
)


class ReportEditError(ValueError):
    """La edición no corresponde a un texto editable o es demasiado larga."""


@dataclass(frozen=True)
class EditableField:
    key: str
    label: str
    default: str


def group_subject(career: str, group_name: str) -> str:
    return f"{career}\x1f{group_name}"


def editable_fields(source, report_type: str) -> list[EditableField]:
    """Campos de texto que el PDF imprime, en el orden en que aparecen."""
    if report_type == "group":
        return [
            EditableField("introduction", "Introducción", source.introduction),
            EditableField("notes", "Notas para el tutor del grupo (opcional)", ""),
        ]
    if report_type == "student":
        fields = [EditableField("student_introduction", "Introducción",
                                source["student_introduction"])]
        for line in source["areas"]:
            # El reporte del alumno sólo imprime recomendaciones en amarillo/rojo.
            if line.traffic_light in ("Rojo", "Amarillo") and line.recommendation:
                fields.append(EditableField(
                    f"recommendation:{line.area_code}",
                    f"Recomendación · {line.area_name}",
                    line.recommendation,
                ))
        fields += [
            EditableField("disclaimer", "Aviso final", source["disclaimer"]),
            EditableField("notes", "Mensaje de Orientación para el alumno (opcional)",
                          ""),
        ]
        return fields
    if report_type == "tutor":
        fields = [EditableField("introduction", "Introducción",
                                source.get("introduction", ""))]
        for line in source["areas"]:
            fields.append(EditableField(
                f"interpretation:{line.area_code}",
                f"Interpretación · {line.area_name}",
                line.interpretation,
            ))
            if line.recommendation:
                fields.append(EditableField(
                    f"recommendation:{line.area_code}",
                    f"Acción sugerida · {line.area_name}",
                    line.recommendation,
                ))
        fields += [
            EditableField("disclaimer", "Aviso final", source["disclaimer"]),
            EditableField("notes", "Notas de Orientación (opcional)", ""),
        ]
        return fields
    raise ReportEditError("Tipo de reporte desconocido.")


def editable_texts(source, report_type: str) -> dict[str, str]:
    return {field.key: field.default for field in editable_fields(source, report_type)}


def load_edits(
    connection: sqlite3.Connection, report_type: str, subject: str
) -> dict[str, str]:
    return dict(connection.execute(
        "SELECT field, value FROM report_edits "
        "WHERE report_type = ? AND subject = ? ORDER BY field",
        (report_type, subject),
    ).fetchall())


def last_edited_at(
    connection: sqlite3.Connection, report_type: str, subject: str
) -> str | None:
    row = connection.execute(
        "SELECT MAX(updated_at) FROM report_edits "
        "WHERE report_type = ? AND subject = ?",
        (report_type, subject),
    ).fetchone()
    return row[0]


def save_edits(
    connection: sqlite3.Connection,
    report_type: str,
    subject: str,
    values: dict[str, str],
    defaults: dict[str, str],
) -> None:
    """Guarda sólo lo que difiere del original; vacío restaura el original."""
    if report_type not in REPORT_TYPES:
        raise ReportEditError("Tipo de reporte desconocido.")
    unknown = set(values) - set(defaults)
    if unknown:
        raise ReportEditError("Sólo se pueden editar los textos del reporte.")
    cleaned = {key: str(value).strip() for key, value in values.items()}
    if any(len(value) > MAX_TEXT_LENGTH for value in cleaned.values()):
        raise ReportEditError(
            f"Cada texto admite como máximo {MAX_TEXT_LENGTH} caracteres."
        )
    now = datetime.now(UTC).isoformat(timespec="seconds")
    with connection:
        for key, value in cleaned.items():
            if not value or value == defaults[key].strip():
                connection.execute(
                    "DELETE FROM report_edits "
                    "WHERE report_type = ? AND subject = ? AND field = ?",
                    (report_type, subject, key),
                )
            else:
                connection.execute(
                    "INSERT INTO report_edits "
                    "(report_type, subject, field, value, updated_at) "
                    "VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT (report_type, subject, field) "
                    "DO UPDATE SET value = excluded.value, "
                    "updated_at = excluded.updated_at",
                    (report_type, subject, key, value, now),
                )


def clear_edits(connection: sqlite3.Connection, report_type: str, subject: str) -> None:
    with connection:
        connection.execute(
            "DELETE FROM report_edits WHERE report_type = ? AND subject = ?",
            (report_type, subject),
        )


def apply_edits(source, report_type: str, edits: dict[str, str]):
    """Devuelve una copia con los textos editados; no toca cifras ni semáforos."""
    if report_type == "group":
        return replace(
            source,
            introduction=edits.get("introduction", source.introduction),
            notes=edits.get("notes", ""),
        )
    data = dict(source)
    lines = []
    for line in data.get("areas", []):
        changes = {}
        if f"recommendation:{line.area_code}" in edits:
            changes["recommendation"] = edits[f"recommendation:{line.area_code}"]
        if f"interpretation:{line.area_code}" in edits:
            changes["interpretation"] = edits[f"interpretation:{line.area_code}"]
        lines.append(replace(line, **changes) if changes else line)
    if "areas" in data:
        data["areas"] = lines
    if "recommendations" in data:
        data["recommendations"] = [
            (line.area_name, line.recommendation)
            for line in lines
            if line.recommendation
        ]
    for key in ("introduction", "student_introduction", "disclaimer"):
        if key in edits and key in data:
            data[key] = edits[key]
    data["notes"] = edits.get("notes", "")
    return data
