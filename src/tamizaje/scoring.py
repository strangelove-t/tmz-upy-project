"""Cálculo versionado de resultados por área."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from tamizaje.normalization import normalize_text
from tamizaje.scoring_config import ScoringConfig


@dataclass(frozen=True)
class AreaResult:
    area_code: str
    raw_average: Decimal | None
    normalized_score: Decimal | None
    traffic_light: str | None
    valid_item_count: int
    applicable_item_count: int
    expected_item_count: int
    is_complete: bool
    scoring_version: str
    issues: tuple[str, ...] = ()


def score_responses(
    responses: Mapping[str, str], config: ScoringConfig
) -> tuple[AreaResult, ...]:
    """Calcula todas las áreas sin inferir reglas fuera de la configuración."""
    option_by_label = {}
    for option in config.options:
        for label in (option.response, option.response_alias):
            if label is not None:
                option_by_label[
                    (option.question_code, normalize_text(label).casefold())
                ] = option

    results = []
    for area in config.areas:
        area_items = [item for item in config.items if item.area_code == area.area_code]
        weighted_sum = Decimal("0")
        weight_sum = Decimal("0")
        valid_count = 0
        excluded_count = 0
        issues = []

        for item in area_items:
            response = responses.get(item.question_code)
            if response is None or not normalize_text(response):
                issues.append(f"missing_response:{item.question_code}")
                continue
            option = option_by_label.get(
                (item.question_code, normalize_text(response).casefold())
            )
            if option is None:
                issues.append(f"unknown_response:{item.question_code}")
                continue
            if not option.include_in_average:
                excluded_count += 1
                continue
            if option.corrected_value is None:
                issues.append(f"missing_value:{item.question_code}")
                continue
            weighted_sum += option.corrected_value * item.weight
            weight_sum += item.weight
            valid_count += 1

        applicable_count = area.expected_item_count - excluded_count
        required_valid_count = min(
            area.minimum_valid_item_count, applicable_count
        )
        is_complete = valid_count >= required_valid_count and weight_sum > 0
        raw_average = weighted_sum / weight_sum if is_complete and weight_sum else None
        normalized_score = (
            (raw_average - config.scale_min)
            / (config.scale_max - config.scale_min)
            * Decimal("100")
            if raw_average is not None
            else None
        )
        if normalized_score is None:
            traffic_light = None
        elif normalized_score >= area.green_min:
            traffic_light = "Verde"
        elif normalized_score >= area.yellow_min:
            traffic_light = "Amarillo"
        else:
            traffic_light = "Rojo"

        results.append(
            AreaResult(
                area_code=area.area_code,
                raw_average=raw_average,
                normalized_score=normalized_score,
                traffic_light=traffic_light,
                valid_item_count=valid_count,
                applicable_item_count=applicable_count,
                expected_item_count=area.expected_item_count,
                is_complete=is_complete,
                scoring_version=config.version,
                issues=tuple(issues),
            )
        )

    return tuple(results)
