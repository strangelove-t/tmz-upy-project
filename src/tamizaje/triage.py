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


def explain_priority(case: TriageComponents, case_level: str) -> str:
    """Texto breve con los componentes que determinan la posición del caso."""
    parts = []
    if case.requested_contact:
        parts.append("solicitó contacto")
    parts.append(f"nivel {case_level}")
    if case.lowest_area_score is not None:
        parts.append(f"área más baja {case.lowest_area_score:.1f}")
    parts.append(f"{case.priority_alert_count} alertas prioritarias")
    parts.append(f"{case.total_alert_count} alertas en total")
    return " · ".join(parts)
