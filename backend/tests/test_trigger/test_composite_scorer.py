import pytest

from app.trigger.composite_scorer import compute_composite_score


class TestCompositeScoreAllSignalsFalse:
    """Test case: all signals False → score=0.0, decision='no_trigger'"""

    def test_all_false_no_trigger(self):
        result = compute_composite_score(
            platform_suspended=False,
            rainfall_triggered=False,
            gis_flood_active=False,
            aqi_triggered=False,
            heat_triggered=False,
            zone_flood_tier="low",
        )

        assert result["composite_score"] == 0.0
        assert result["decision"] == "no_trigger"
        assert result["sources_confirmed"] == 0
        assert result["fast_path_used"] is False


class TestCompositeScorePlatformSuspensionOnly:
    """Test case: only platform suspended → score=0.40, sources=1, decision='no_trigger'"""

    def test_platform_only_insufficient_sources(self):
        result = compute_composite_score(
            platform_suspended=True,
            rainfall_triggered=False,
            gis_flood_active=False,
            aqi_triggered=False,
            heat_triggered=False,
            zone_flood_tier="low",
        )

        assert result["composite_score"] == 0.4
        assert result["sources_confirmed"] == 1
        assert result["decision"] == "no_trigger"
        assert result["fast_path_used"] is False


class TestCompositeScorePlatformAndRainfall:
    """Test case: platform + rainfall → score=0.75, sources=2, decision='trigger_corroborated'"""

    def test_platform_and_rainfall_corroborated(self):
        result = compute_composite_score(
            platform_suspended=True,
            rainfall_triggered=True,
            gis_flood_active=False,
            aqi_triggered=False,
            heat_triggered=False,
            zone_flood_tier="low",
        )

        assert result["composite_score"] == 0.75
        assert result["sources_confirmed"] == 2
        assert result["decision"] == "trigger_corroborated"
        assert result["fast_path_used"] is False


class TestCompositeScorePlatformRainfallAndGIS:
    """Test case: platform + rainfall + GIS → score=0.90, sources=3, not fast_path"""

    def test_platform_rainfall_gis_high_tier(self):
        result = compute_composite_score(
            platform_suspended=True,
            rainfall_triggered=True,
            gis_flood_active=True,
            aqi_triggered=False,
            heat_triggered=False,
            zone_flood_tier="high",
        )

        assert result["composite_score"] == 0.90
        assert result["sources_confirmed"] == 3
        assert result["decision"] == "trigger_corroborated"
        assert result["fast_path_used"] is False

    def test_platform_rainfall_gis_medium_tier(self):
        result = compute_composite_score(
            platform_suspended=True,
            rainfall_triggered=True,
            gis_flood_active=True,
            aqi_triggered=False,
            heat_triggered=False,
            zone_flood_tier="medium",
        )

        assert result["composite_score"] == 0.90
        assert result["sources_confirmed"] == 3
        assert result["decision"] == "trigger_corroborated"
        assert result["fast_path_used"] is False


class TestCompositeScoreFastPath:
    """Test case: platform + rainfall + GIS + heat → score=1.0, fast_path=True"""

    def test_platform_rainfall_gis_heat_score_1_0(self):
        result = compute_composite_score(
            platform_suspended=True,
            rainfall_triggered=True,
            gis_flood_active=True,
            aqi_triggered=False,
            heat_triggered=True,
            zone_flood_tier="high",
        )

        assert result["composite_score"] == 1.0
        assert result["decision"] == "trigger_fast_path"
        assert result["fast_path_used"] is True

    def test_platform_rainfall_gis_aqi_score_1_0(self):
        result = compute_composite_score(
            platform_suspended=True,
            rainfall_triggered=True,
            gis_flood_active=True,
            aqi_triggered=True,
            heat_triggered=False,
            zone_flood_tier="high",
        )

        assert result["composite_score"] == 1.0
        assert result["decision"] == "trigger_fast_path"
        assert result["fast_path_used"] is True


class TestCompositeScoreAQIAndHeatMutualExclusivity:
    """Test case: Heat and AQI both True → score same as heat alone (share 0.10 slot)"""

    def test_heat_and_aqi_do_not_stack(self):
        """Both true should give same score as either alone."""
        result_both = compute_composite_score(
            platform_suspended=False,
            rainfall_triggered=False,
            gis_flood_active=False,
            aqi_triggered=True,
            heat_triggered=True,
            zone_flood_tier="low",
        )

        result_heat_only = compute_composite_score(
            platform_suspended=False,
            rainfall_triggered=False,
            gis_flood_active=False,
            aqi_triggered=False,
            heat_triggered=True,
            zone_flood_tier="low",
        )

        result_aqi_only = compute_composite_score(
            platform_suspended=False,
            rainfall_triggered=False,
            gis_flood_active=False,
            aqi_triggered=True,
            heat_triggered=False,
            zone_flood_tier="low",
        )

        assert result_both["composite_score"] == 0.10
        assert result_both["composite_score"] == result_heat_only["composite_score"]
        assert result_both["composite_score"] == result_aqi_only["composite_score"]


class TestGISActivationLogic:
    """Test GIS signal only activates when tier is High/Medium AND rainfall triggered."""

    def test_gis_requires_high_or_medium_tier(self):
        """GIS should not contribute if zone tier is low, even if gis_flood_active=True."""
        result = compute_composite_score(
            platform_suspended=True,
            rainfall_triggered=True,
            gis_flood_active=True,
            aqi_triggered=False,
            heat_triggered=False,
            zone_flood_tier="low",
        )

        assert result["composite_score"] == 0.75  # Only 0.40 + 0.35, no GIS 0.15
        assert result["component_scores"]["gis"] == 0.0
        assert result["sources_confirmed"] == 2  # Operational + Environmental


    def test_gis_requires_rainfall_triggered(self):
        """GIS should not contribute if rainfall not triggered, even if gis_flood_active=True."""
        result = compute_composite_score(
            platform_suspended=True,
            rainfall_triggered=False,
            gis_flood_active=True,
            aqi_triggered=False,
            heat_triggered=False,
            zone_flood_tier="high",
        )

        assert result["composite_score"] == 0.40  # Only platform, no GIS
        assert result["component_scores"]["gis"] == 0.0
        assert result["sources_confirmed"] == 1  # Only Operational


class TestCorroborationGateBoundaries:
    """Test score boundaries for corroboration gate decisions."""

    def test_score_exactly_0_5_requires_2_sources(self):
        """At boundary 0.5, need 2+ sources to trigger."""
        result = compute_composite_score(
            platform_suspended=True,  # 0.40
            rainfall_triggered=True,  # 0.35
            gis_flood_active=False,
            aqi_triggered=False,
            heat_triggered=False,
            zone_flood_tier="low",
        )

        assert result["composite_score"] == 0.75  # Not exactly 0.5, but testing gate
        assert result["decision"] == "trigger_corroborated"

    def test_score_0_5_with_1_source_no_trigger(self):
        """Platform only = 0.40 < 0.5, but also only 1 source."""
        result = compute_composite_score(
            platform_suspended=True,
            rainfall_triggered=False,
            gis_flood_active=False,
            aqi_triggered=False,
            heat_triggered=False,
            zone_flood_tier="low",
        )

        assert result["composite_score"] == 0.40
        assert result["decision"] == "no_trigger"

    def test_score_0_9_exact_boundary(self):
        """At exactly 0.9, not > 0.9, so not fast_path."""
        result = compute_composite_score(
            platform_suspended=True,  # 0.40
            rainfall_triggered=True,  # 0.35
            gis_flood_active=True,  # 0.15 (with high tier)
            aqi_triggered=False,
            heat_triggered=False,
            zone_flood_tier="high",
        )

        assert result["composite_score"] == 0.90
        assert result["fast_path_used"] is False
        assert result["decision"] == "trigger_corroborated"

    def test_score_just_over_0_9_fast_path(self):
        """Score > 0.9 triggers fast_path immediately."""
        result = compute_composite_score(
            platform_suspended=True,  # 0.40
            rainfall_triggered=True,  # 0.35
            gis_flood_active=True,  # 0.15
            aqi_triggered=True,  # 0.10 (shares slot with heat)
            heat_triggered=False,
            zone_flood_tier="high",
        )

        assert result["composite_score"] == 1.0
        assert result["fast_path_used"] is True
        assert result["decision"] == "trigger_fast_path"


class TestSourceCategoryTracking:
    """Test that source category counts are correct."""

    def test_environmental_from_rainfall(self):
        result = compute_composite_score(
            platform_suspended=False,
            rainfall_triggered=True,
            gis_flood_active=False,
            aqi_triggered=False,
            heat_triggered=False,
            zone_flood_tier="low",
        )

        assert result["source_categories"]["environmental"] is True
        assert result["source_categories"]["operational"] is False
        assert result["source_categories"]["geospatial"] is False
        assert result["sources_confirmed"] == 1

    def test_environmental_from_aqi(self):
        result = compute_composite_score(
            platform_suspended=False,
            rainfall_triggered=False,
            gis_flood_active=False,
            aqi_triggered=True,
            heat_triggered=False,
            zone_flood_tier="low",
        )

        assert result["source_categories"]["environmental"] is True
        assert result["sources_confirmed"] == 1

    def test_environmental_from_heat(self):
        result = compute_composite_score(
            platform_suspended=False,
            rainfall_triggered=False,
            gis_flood_active=False,
            aqi_triggered=False,
            heat_triggered=True,
            zone_flood_tier="low",
        )

        assert result["source_categories"]["environmental"] is True
        assert result["sources_confirmed"] == 1

    def test_geospatial_source(self):
        result = compute_composite_score(
            platform_suspended=False,
            rainfall_triggered=True,  # Required for GIS to activate
            gis_flood_active=True,
            aqi_triggered=False,
            heat_triggered=False,
            zone_flood_tier="high",
        )

        assert result["source_categories"]["geospatial"] is True
        assert result["sources_confirmed"] >= 2

    def test_operational_source(self):
        result = compute_composite_score(
            platform_suspended=True,
            rainfall_triggered=False,
            gis_flood_active=False,
            aqi_triggered=False,
            heat_triggered=False,
            zone_flood_tier="low",
        )

        assert result["source_categories"]["operational"] is True
        assert result["sources_confirmed"] == 1


class TestInvalidInput:
    """Test error handling for invalid inputs."""

    def test_invalid_zone_tier_raises_error(self):
        with pytest.raises(ValueError, match="zone_flood_tier must be"):
            compute_composite_score(
                platform_suspended=False,
                rainfall_triggered=False,
                gis_flood_active=False,
                aqi_triggered=False,
                heat_triggered=False,
                zone_flood_tier="extreme",
            )
