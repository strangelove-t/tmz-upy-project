"""Orden de atención lexicográfico y explicable; no es una fórmula clínica."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class TriageComponents:
    requested_contact: bool
    case_level_rank: int
    lowest_area_score: Decimal | None
    priority_alert_count: int
    total_alert_count: int
    detected_at: str


def triage_key(case: TriageComponents) -> tuple:
    """Ordena: solicitud de contacto, severidad, menor área, alertas, antigüedad."""
    return (
        not case.requested_contact,
        case.case_level_rank,
        case.lowest_area_score is None,
        case.lowest_area_score if case.lowest_area_score is not None else Decimal(0),
        -case.priority_alert_count,
        -case.total_alert_count,
        case.detected_at,
    )


def explain_priority(
    case: TriageComponents, case_level: str, critical_area_name: str | None = None
) -> str:
    """Explica en lenguaje cotidiano por qué el caso ocupa su posición."""
    parts = []
    if case.requested_contact:
        parts.append("Pidió que Orientación se ponga en contacto.")
    parts.append(f"Nivel: {case_level}.")
    total = case.total_alert_count
    if case.priority_alert_count:
        if total == 1:
            parts.append("Su alerta es de atención prioritaria.")
        else:
            parts.append(
                f"{case.priority_alert_count} de sus {total} alertas son de "
                "atención prioritaria."
            )
    else:
        parts.append(f"Tiene {total} alerta{'s' if total != 1 else ''}.")
    if case.lowest_area_score is not None and critical_area_name:
        parts.append(
            f"Área con puntaje más bajo: {critical_area_name} "
            f"({case.lowest_area_score:.0f} de 100)."
        )
    return " ".join(parts)
