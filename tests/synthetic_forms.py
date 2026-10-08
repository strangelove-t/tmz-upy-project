"""Exportaciones de Forms completamente sintéticas basadas en el catálogo real.

Nunca contienen datos institucionales: todos los valores se generan aquí.
"""

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path

from tamizaje.models import EngineConfig, load_engine_config
from tamizaje.questionnaire import QuestionDefinition, load_questionnaire

CONFIG_DIR = Path(__file__).parents[1] / "config"


def project_config() -> tuple[tuple[QuestionDefinition, ...], EngineConfig]:
    return (
        load_questionnaire(CONFIG_DIR / "questionnaire.csv"),
        load_engine_config(CONFIG_DIR),
    )


def best_answers(engine: EngineConfig) -> dict[str, str]:
    """Respuestas con mayor fortaleza en cada reactivo y sin detonantes."""
    best: dict[str, tuple] = {}
    for option in engine.scoring.options:
        if option.corrected_value is None:
            continue
        current = best.get(option.question_code)
        if current is None or option.corrected_value > current[0]:
            best[option.question_code] = (option.corrected_value, option.response)
    return {code: response for code, (_, response) in best.items()}


def synthetic_rows(
    questionnaire: Sequence[QuestionDefinition],
    engine: EngineConfig,
    students: Sequence[Mapping[str, str]],
) -> bytes:
    """Genera un CSV con una fila por estudiante; cada dict sobrescribe códigos."""
    defaults = best_answers(engine)
    stream = io.StringIO()
    writer = csv.writer(stream, delimiter=";")
    writer.writerow(question.question_text for question in questionnaire)
    for index, overrides in enumerate(students, start=1):
        base = {
            "ADM_RESPONSE_ID": f"synthetic-{index:03d}",
            "ADM_STARTED_AT": "2026-01-01 09:00",
            "ADM_COMPLETED_AT": "2026-01-01 09:20",
            "ADM_EMAIL": f"synthetic{index:03d}@example.edu",
            "ADM_NAME": f"Estudiante Sintético {index:03d}",
            "DG02": "Carrera Sintética",
            "DG03": "G-01",
            "DC01": "",
            "DC03": "",
        }
        base.update(overrides)
        writer.writerow(
            base.get(
                question.question_code,
                defaults.get(question.question_code, "No"),
            )
            for question in questionnaire
        )
    return stream.getvalue().encode("utf-8")
