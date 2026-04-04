"""Deterministic behavioral fraud signals."""


def compute_activity_7d_score(deliveries_7d: int, avg_daily_30d: float) -> float:
    if avg_daily_30d == 0:
        return 0.5

    ratio = deliveries_7d / (avg_daily_30d * 7)
    return float(min(ratio, 1.5))


def compute_enrollment_recency_score(enrollment_week: int) -> float:
    score = 1 - (enrollment_week / 26)
    return float(max(0.0, min(score, 1.0)))


def check_rain_paradox(zone_flood_tier: str, zone_order_volume_ratio: float) -> bool:
    return zone_flood_tier == "low" and zone_order_volume_ratio > 1.10


def check_conditional_baseline_floor(activity_dropped: bool, disruption_was_forecast: bool) -> bool:
    return activity_dropped and disruption_was_forecast