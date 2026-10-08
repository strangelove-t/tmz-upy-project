"""Contratos compartidos entre el motor y la aplicación."""

from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from tamizaje.alerts import AlertConfig, load_alert_config
from tamizaje.recommendations import Recommendation, load_recommendations
from tamizaje.scoring_config import ScoringConfig, load_scoring_config


class EngineConfigError(ValueError):
    """La configuración general del motor es inválida."""


@dataclass(frozen=True)
class EngineConfig:
    scoring: ScoringConfig
    alerts: AlertConfig
    recommendations: tuple[Recommendation, ...]
    minimum_group_size: int
    report_timezone: ZoneInfo


def load_engine_config(config_dir: Path) -> EngineConfig:
    """Carga y valida en conjunto scoring, alertas y recomendaciones activas."""
    scoring = load_scoring_config(config_dir)
    try:
        parameters = yaml.safe_load(
            (config_dir / "parameters.yaml").read_text(encoding="utf-8")
        )
        minimum_group_size = int(parameters["minimum_group_size"])
        report_timezone = ZoneInfo(str(parameters["report_timezone"]))
    except (
        KeyError,
        TypeError,
        ValueError,
        OSError,
        yaml.YAMLError,
        ZoneInfoNotFoundError,
    ) as error:
        raise EngineConfigError("parameters.yaml no cumple el contrato.") from error
    if minimum_group_size < 1:
        raise EngineConfigError("minimum_group_size debe ser positivo.")
    return EngineConfig(
        scoring=scoring,
        alerts=load_alert_config(config_dir),
        recommendations=load_recommendations(config_dir, scoring),
        minimum_group_size=minimum_group_size,
        report_timezone=report_timezone,
    )
