"""Recomendaciones versionadas por área y semáforo."""

import csv
from dataclasses import dataclass
from pathlib import Path

from tamizaje.scoring import AreaResult
from tamizaje.scoring_config import ScoringConfig

RECOMMENDATION_COLUMNS = (
    "RecommendationCode",
    "AreaCode",
    "TrafficLight",
    "StudentRecommendation",
    "StaffRecommendation",
    "Version",
)
TRAFFIC_LIGHTS = ("Verde", "Amarillo", "Rojo")


class RecommendationConfigError(ValueError):
    """El catálogo de recomendaciones es inválido."""


@dataclass(frozen=True)
class Recommendation:
    recommendation_code: str
    area_code: str
    traffic_light: str
    student_recommendation: str
    staff_recommendation: str
    version: str


def load_recommendations(
    config_dir: Path, scoring_config: ScoringConfig
) -> tuple[Recommendation, ...]:
    """Exige una recomendación por área y semáforo de la versión de scoring."""
    path = config_dir / "recommendations.csv"
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != RECOMMENDATION_COLUMNS:
                raise RecommendationConfigError(
                    "Los encabezados de recommendations.csv no cumplen el contrato."
                )
            rows = list(reader)
    except OSError as error:
        raise RecommendationConfigError(
            "No fue posible leer recommendations.csv."
        ) from error

    area_codes = {area.area_code for area in scoring_config.areas}
    recommendations: list[Recommendation] = []
    seen_codes: set[str] = set()
    seen_keys: set[tuple[str, str]] = set()
    for row_number, row in enumerate(rows, start=2):
        if row["Version"].strip() != scoring_config.version:
            continue
        recommendation = Recommendation(
            recommendation_code=row["RecommendationCode"].strip(),
            area_code=row["AreaCode"].strip(),
            traffic_light=row["TrafficLight"].strip(),
            student_recommendation=row["StudentRecommendation"].strip(),
            staff_recommendation=row["StaffRecommendation"].strip(),
            version=scoring_config.version,
        )
        key = (recommendation.area_code, recommendation.traffic_light)
        if (
            not recommendation.recommendation_code
            or recommendation.recommendation_code in seen_codes
            or recommendation.area_code not in area_codes
            or recommendation.traffic_light not in TRAFFIC_LIGHTS
            or not recommendation.student_recommendation
            or not recommendation.staff_recommendation
            or key in seen_keys
        ):
            raise RecommendationConfigError(
                f"Fila inválida en recommendations.csv:{row_number}."
            )
        seen_codes.add(recommendation.recommendation_code)
        seen_keys.add(key)
        recommendations.append(recommendation)

    if len(seen_keys) != len(area_codes) * len(TRAFFIC_LIGHTS):
        raise RecommendationConfigError(
            "recommendations.csv no cubre todas las áreas y semáforos."
        )
    return tuple(recommendations)


def recommendation_for(
    result: AreaResult, recommendations: tuple[Recommendation, ...]
) -> Recommendation | None:
    """Un área incompleta no recibe recomendación automática."""
    if not result.is_complete or result.traffic_light is None:
        return None
    for recommendation in recommendations:
        if (
            recommendation.area_code == result.area_code
            and recommendation.traffic_light == result.traffic_light
            and recommendation.version == result.scoring_version
        ):
            return recommendation
    return None
