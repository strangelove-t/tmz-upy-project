"""Consolidación de alertas en un solo caso por envío."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from tamizaje.alerts import AlertConfig, TriggeredAlert
from tamizaje.scoring import AreaResult

SOURCE_STUDENT_REQUEST = "Solicitud del alumno"
SOURCE_AUTOMATIC = "Alerta automática"

CASE_STATUSES = ("Nuevo", "En seguimiento", "Canalizado", "Cerrado")
CONTACT_STATUSES = ("Sin contacto", "Contactado", "No localizado", "Cita agendada")


@dataclass(frozen=True)
class ConsolidatedCase:
    case_level: str
    case_level_rank: int
    case_source: str
    requested_contact: bool
    lowest_area_score: Decimal | None
    critical_area_code: str | None
    priority_alert_count: int
    total_alert_count: int
    initial_reason: str


def consolidate_case(
    alerts: Sequence[TriggeredAlert],
    area_results: Sequence[AreaResult],
    config: AlertConfig,
) -> ConsolidatedCase | None:
    """Sin alertas no hay caso; con una o más se crea exactamente uno."""
    if not alerts:
        return None

    rank_by_level = {level: rank for rank, level in enumerate(config.levels, start=1)}
    top_alert = min(alerts, key=lambda alert: rank_by_level[alert.alert_level])
    requested_contact = any(
        alert.alert_category == config.contact_request_category for alert in alerts
    )

    complete = [
        result
        for result in area_results
        if result.is_complete and result.normalized_score is not None
    ]
    critical = min(
        complete,
        key=lambda result: (result.normalized_score, result.area_code),
        default=None,
    )

    return ConsolidatedCase(
        case_level=top_alert.alert_level,
        case_level_rank=rank_by_level[top_alert.alert_level],
        case_source=SOURCE_STUDENT_REQUEST if requested_contact else SOURCE_AUTOMATIC,
        requested_contact=requested_contact,
        lowest_area_score=critical.normalized_score if critical else None,
        critical_area_code=critical.area_code if critical else None,
        priority_alert_count=sum(
            alert.alert_level == config.levels[0] for alert in alerts
        ),
        total_alert_count=len(alerts),
        initial_reason=top_alert.alert_reason,
    )
