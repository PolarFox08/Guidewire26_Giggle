"""Composite trigger score calculation and corroboration gate logic.

Scoring rules from Section 1.7:
- Platform suspension: 0.40 weight
- Rainfall at IMD threshold: 0.35 weight
- GIS flood zone activation: 0.15 weight (only if High/Medium tier AND rainfall triggered)
- AQI severe or Heat severe: 0.10 weight (mutually exclusive — they share this slot)

Corroboration gate:
- Score < 0.5 → no_trigger
- Score 0.5–0.9 → requires 2+ of 3 source categories
- Score > 0.9 → fast_path automatic trigger
"""

from __future__ import annotations


def compute_composite_score(
    platform_suspended: bool,
    rainfall_triggered: bool,
    gis_flood_active: bool,
    aqi_triggered: bool,
    heat_triggered: bool,
    zone_flood_tier: str,
) -> dict:
    """Compute composite trigger score and determine routing decision.

    Args:
        platform_suspended: True if platform zone API reports suspended
        rainfall_triggered: True if rainfall >= 64.5 mm/24h (IMD Heavy threshold)
        gis_flood_active: True if OpenCity flood zone is active for this zone
        aqi_triggered: True if AQI > 300 for 4 consecutive hours
        heat_triggered: True if temperature >= 45°C for 4+ consecutive hours
        zone_flood_tier: 'high', 'medium', or 'low' — from OpenCity GIS

    Returns:
        dict with:
            - composite_score: float 0.0–1.0
            - sources_confirmed: int 0–3 (count of independent source categories active)
            - decision: 'no_trigger', 'trigger_corroborated', or 'trigger_fast_path'
            - fast_path_used: bool
    """
    if zone_flood_tier not in ("high", "medium", "low"):
        raise ValueError(f"zone_flood_tier must be 'high', 'medium', or 'low', got {zone_flood_tier!r}")

    # Calculate component scores
    platform_score = 0.40 if platform_suspended else 0.0
    rainfall_score = 0.35 if rainfall_triggered else 0.0

    # GIS activation requires High/Medium tier AND rainfall triggered
    gis_score = (
        0.15
        if (
            gis_flood_active
            and zone_flood_tier in ("high", "medium")
            and rainfall_triggered
        )
        else 0.0
    )

    # AQI and heat are mutually exclusive — take whichever is active (or neither)
    # If both are true, they still share the 0.10 slot (do not stack)
    aqi_heat_score = 0.0
    if aqi_triggered or heat_triggered:
        aqi_heat_score = 0.10

    # Composite score is sum of all components, capped at 1.0
    composite_score = min(1.0, platform_score + rainfall_score + gis_score + aqi_heat_score)

    # Count independent source categories confirmed
    # Source 1: Environmental = rainfall OR aqi OR heat
    environmental_active = rainfall_triggered or aqi_triggered or heat_triggered
    # Source 2: Geospatial = GIS flood zone active
    geospatial_active = gis_score > 0.0
    # Source 3: Operational = platform suspended
    operational_active = platform_suspended

    sources_confirmed = sum([environmental_active, geospatial_active, operational_active])

    # Corroboration gate: determine decision based on score and source count
    if composite_score < 0.5:
        decision = "no_trigger"
        fast_path_used = False
    elif composite_score > 0.9:
        decision = "trigger_fast_path"
        fast_path_used = True
    else:  # 0.5 <= score <= 0.9
        if sources_confirmed >= 2:
            decision = "trigger_corroborated"
            fast_path_used = False
        else:
            decision = "no_trigger"
            fast_path_used = False

    return {
        "composite_score": round(composite_score, 3),
        "sources_confirmed": sources_confirmed,
        "decision": decision,
        "fast_path_used": fast_path_used,
        "component_scores": {
            "platform": round(platform_score, 2),
            "rainfall": round(rainfall_score, 2),
            "gis": round(gis_score, 2),
            "aqi_heat": round(aqi_heat_score, 2),
        },
        "source_categories": {
            "environmental": environmental_active,
            "geospatial": geospatial_active,
            "operational": operational_active,
        },
    }
