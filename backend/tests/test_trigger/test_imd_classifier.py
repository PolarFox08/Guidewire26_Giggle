import pytest

from app.trigger.imd_classifier import check_aqi_trigger, classify_heat, classify_rainfall


def test_classify_rainfall_below_heavy_threshold_not_triggered():
    result = classify_rainfall(64.4)

    assert result["triggered"] is False
    assert result["category"] is None
    assert result["signal_weight"] == 0.0


def test_classify_rainfall_heavy_boundary_triggered():
    result = classify_rainfall(64.5)

    assert result["triggered"] is True
    assert result["category"] == "heavy_rain"
    assert result["signal_weight"] == 0.35


def test_classify_rainfall_very_heavy_boundary_triggered():
    result = classify_rainfall(115.6)

    assert result["triggered"] is True
    assert result["category"] == "very_heavy_rain"
    assert result["signal_weight"] == 0.35


def test_classify_rainfall_extreme_heavy_boundary_triggered():
    result = classify_rainfall(204.4)

    assert result["triggered"] is True
    assert result["category"] == "extreme_heavy_rain"
    assert result["signal_weight"] == 0.35


def test_classify_heat_below_threshold_not_triggered():
    result = classify_heat(44.9)

    assert result["triggered"] is False
    assert result["signal_weight"] == 0.0


def test_classify_heat_boundary_triggered():
    result = classify_heat(45.0)

    assert result["triggered"] is True
    assert result["signal_weight"] == 0.10


def test_check_aqi_trigger_true_when_last_four_above_300():
    result = check_aqi_trigger([280, 310, 320, 330, 340])

    assert result["triggered"] is True
    assert result["signal_weight"] == 0.10


def test_check_aqi_trigger_false_when_any_last_four_not_above_300():
    result = check_aqi_trigger([305, 301, 300, 320])

    assert result["triggered"] is False
    assert result["signal_weight"] == 0.0


def test_check_aqi_trigger_false_when_less_than_four_readings():
    result = check_aqi_trigger([350, 360, 370])

    assert result["triggered"] is False
    assert result["required_readings"] == 4
    assert result["available_readings"] == 3


def test_classify_rainfall_rejects_negative_values():
    with pytest.raises(ValueError):
        classify_rainfall(-0.1)


def test_check_aqi_trigger_rejects_non_sequence_input():
    with pytest.raises(TypeError):
        check_aqi_trigger("301,302,303,304")
