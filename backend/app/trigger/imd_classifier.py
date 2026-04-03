"""IMD and CPCB threshold classifiers used by the trigger engine."""

from __future__ import annotations

import math
from collections.abc import Sequence

HEAVY_RAIN_MM_24H = 64.5
VERY_HEAVY_RAIN_MM_24H = 115.6
EXTREME_HEAVY_RAIN_MM_24H = 204.4
SEVERE_HEAT_C = 45.0
SEVERE_AQI_THRESHOLD = 300.0
SEVERE_AQI_CONSECUTIVE_HOURS = 4

RAINFALL_SIGNAL_WEIGHT = 0.35
HEAT_SIGNAL_WEIGHT = 0.10
AQI_SIGNAL_WEIGHT = 0.10


def _validate_finite_number(value: float, field_name: str) -> float:
    if not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a number")

    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise ValueError(f"{field_name} must be a finite number")

    return numeric_value


def classify_rainfall(mm_per_24h: float) -> dict:
    """Classify rainfall according to IMD 24h precipitation thresholds."""
    rainfall = _validate_finite_number(mm_per_24h, "mm_per_24h")
    if rainfall < 0:
        raise ValueError("mm_per_24h cannot be negative")

    if rainfall >= EXTREME_HEAVY_RAIN_MM_24H:
        category = "extreme_heavy_rain"
        triggered = True
    elif rainfall >= VERY_HEAVY_RAIN_MM_24H:
        category = "very_heavy_rain"
        triggered = True
    elif rainfall >= HEAVY_RAIN_MM_24H:
        category = "heavy_rain"
        triggered = True
    else:
        category = None
        triggered = False

    return {
        "triggered": triggered,
        "category": category,
        "signal_weight": RAINFALL_SIGNAL_WEIGHT if triggered else 0.0,
    }


def classify_heat(temp_celsius: float) -> dict:
    """Classify severe heatwave condition from max temperature."""
    temp = _validate_finite_number(temp_celsius, "temp_celsius")

    triggered = temp >= SEVERE_HEAT_C
    return {
        "triggered": triggered,
        "signal_weight": HEAT_SIGNAL_WEIGHT if triggered else 0.0,
    }


def check_aqi_trigger(consecutive_readings: list[float]) -> dict:
    """Check CPCB severe AQI trigger over the latest 4 consecutive readings."""
    if not isinstance(consecutive_readings, Sequence) or isinstance(
        consecutive_readings, (str, bytes)
    ):
        raise TypeError("consecutive_readings must be a sequence of numeric AQI values")

    if len(consecutive_readings) < SEVERE_AQI_CONSECUTIVE_HOURS:
        return {
            "triggered": False,
            "signal_weight": 0.0,
            "required_readings": SEVERE_AQI_CONSECUTIVE_HOURS,
            "available_readings": len(consecutive_readings),
        }

    recent_values = consecutive_readings[-SEVERE_AQI_CONSECUTIVE_HOURS:]
    normalized_values: list[float] = []
    for idx, value in enumerate(recent_values):
        normalized = _validate_finite_number(value, f"consecutive_readings[{idx}]")
        if normalized < 0:
            raise ValueError(f"consecutive_readings[{idx}] cannot be negative")
        normalized_values.append(normalized)

    triggered = all(value > SEVERE_AQI_THRESHOLD for value in normalized_values)

    return {
        "triggered": triggered,
        "signal_weight": AQI_SIGNAL_WEIGHT if triggered else 0.0,
        "required_readings": SEVERE_AQI_CONSECUTIVE_HOURS,
        "available_readings": len(consecutive_readings),
        "threshold": SEVERE_AQI_THRESHOLD,
    }
