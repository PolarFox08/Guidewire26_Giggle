import pytest
import httpx

from app.trigger import aqi_monitor
from app.trigger.aqi_monitor import (
    _to_float,
    _aqi_buffer,
    check_aqi_trigger,
    fetch_aqi_for_zone,
    poll_aqi_all_zones,
    update_aqi_buffer,
)


@pytest.fixture(autouse=True)
def reset_aqi_buffer():
    _aqi_buffer.clear()
    yield
    _aqi_buffer.clear()


def test_check_aqi_trigger_buffer_empty_not_triggered():
    result = check_aqi_trigger(1)

    assert result["triggered"] is False
    assert result["consecutive_readings"] == 0
    assert result["latest_aqi"] is None


def test_check_aqi_trigger_with_three_high_readings_not_triggered():
    update_aqi_buffer(1, 310)
    update_aqi_buffer(1, 320)
    update_aqi_buffer(1, 305)

    result = check_aqi_trigger(1)

    assert result["triggered"] is False
    assert result["consecutive_readings"] == 3
    assert result["latest_aqi"] == 305.0


def test_check_aqi_trigger_true_for_four_consecutive_above_300():
    for value in [310, 320, 305, 315]:
        update_aqi_buffer(1, value)

    result = check_aqi_trigger(1)

    assert result["triggered"] is True
    assert result["consecutive_readings"] == 4
    assert result["latest_aqi"] == 315.0


def test_check_aqi_trigger_false_when_one_of_four_is_not_above_300():
    for value in [310, 295, 305, 315]:
        update_aqi_buffer(1, value)

    result = check_aqi_trigger(1)

    assert result["triggered"] is False
    assert result["consecutive_readings"] == 4
    assert result["latest_aqi"] == 315.0


def test_update_aqi_buffer_keeps_only_last_four_readings():
    for value in [290, 300, 310, 320, 330]:
        update_aqi_buffer(1, value)

    assert len(_aqi_buffer[1]) == 4
    assert _aqi_buffer[1] == [300.0, 310.0, 320.0, 330.0]


def test_to_float_handles_common_edge_cases():
    assert _to_float(True) is None
    assert _to_float(" 301 ") == 301.0
    assert _to_float("not-a-number") is None
    assert _to_float(float("inf")) is None


def test_update_aqi_buffer_rejects_invalid_inputs():
    with pytest.raises(TypeError):
        update_aqi_buffer("1", 310.0)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        update_aqi_buffer(1, "not-numeric")  # type: ignore[arg-type]


def test_check_aqi_trigger_rejects_invalid_zone_type():
    with pytest.raises(TypeError):
        check_aqi_trigger("1")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_fetch_aqi_for_zone_rejects_invalid_zone_id_type():
    result = await fetch_aqi_for_zone("1", 13.0, 80.0)  # type: ignore[arg-type]
    assert result is None


@pytest.mark.asyncio
async def test_fetch_aqi_for_zone_rejects_invalid_station_coordinates():
    result = await fetch_aqi_for_zone(1, "bad", 80.0)  # type: ignore[arg-type]
    assert result is None


@pytest.mark.asyncio
async def test_fetch_aqi_for_zone_returns_none_on_http_error(monkeypatch):
    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            _ = args, kwargs
            raise httpx.HTTPError("network")

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: _Client())

    result = await fetch_aqi_for_zone(1, 13.0, 80.0)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_aqi_for_zone_returns_none_when_records_missing(monkeypatch):
    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"records": []}

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            _ = args, kwargs
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: _Client())

    result = await fetch_aqi_for_zone(1, 13.0, 80.0)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_aqi_for_zone_returns_closest_station_value(monkeypatch):
    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "records": [
                    {"latitude": "13.0000", "longitude": "80.0000", "aqi": "310"},
                    {"latitude": "13.5000", "longitude": "80.5000", "aqi": "420"},
                    {"latitude": "bad", "longitude": "80.1", "aqi": "250"},
                ]
            }

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            _ = args, kwargs
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: _Client())

    result = await fetch_aqi_for_zone(1, 13.01, 80.01)
    assert result == 310.0


@pytest.mark.asyncio
async def test_poll_aqi_all_zones_rejects_non_list_input():
    with pytest.raises(TypeError):
        await poll_aqi_all_zones("not-a-list")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_poll_aqi_all_zones_skips_invalid_zone_payloads(monkeypatch):
    async def fake_fetch(zone_cluster_id, station_lat, station_lon):
        _ = zone_cluster_id, station_lat, station_lon
        return 305.0

    monkeypatch.setattr(aqi_monitor, "fetch_aqi_for_zone", fake_fetch)

    result = await poll_aqi_all_zones(
        [
            "bad-zone",  # ignored
            {"id": "1", "centroid_lat": 13.0, "centroid_lon": 80.0},  # ignored
            {"id": 2, "centroid_lat": "bad", "centroid_lon": 80.1},  # returns check only
            {"id": 3, "centroid_lat": 13.1, "centroid_lon": 80.1},  # fetched
        ]
    )

    assert 2 in result
    assert result[2]["triggered"] is False
    assert result[2]["latest_aqi"] is None
    assert 3 in result
    assert result[3]["latest_aqi"] == 305.0


@pytest.mark.asyncio
async def test_poll_aqi_all_zones_updates_buffer_and_returns_status(monkeypatch):
    async def fake_fetch(zone_cluster_id, station_lat, station_lon):
        _ = station_lat
        _ = station_lon
        return {1: 310.0, 2: 280.0}[zone_cluster_id]

    monkeypatch.setattr(aqi_monitor, "fetch_aqi_for_zone", fake_fetch)

    zone_clusters = [
        {"id": 1, "centroid_lat": 13.0, "centroid_lon": 80.0},
        {"id": 2, "centroid_lat": 13.1, "centroid_lon": 80.1},
    ]

    result = await poll_aqi_all_zones(zone_clusters)

    assert result[1]["triggered"] is False
    assert result[1]["consecutive_readings"] == 1
    assert result[1]["latest_aqi"] == 310.0

    assert result[2]["triggered"] is False
    assert result[2]["consecutive_readings"] == 1
    assert result[2]["latest_aqi"] == 280.0


@pytest.mark.asyncio
async def test_poll_aqi_all_zones_fetch_none_leaves_buffer_unchanged(monkeypatch):
    update_aqi_buffer(1, 310)
    update_aqi_buffer(1, 320)

    async def fake_fetch(zone_cluster_id, station_lat, station_lon):
        _ = zone_cluster_id
        _ = station_lat
        _ = station_lon
        return None

    monkeypatch.setattr(aqi_monitor, "fetch_aqi_for_zone", fake_fetch)

    result = await poll_aqi_all_zones([
        {"id": 1, "centroid_lat": 13.0, "centroid_lon": 80.0}
    ])

    assert _aqi_buffer[1] == [310.0, 320.0]
    assert result[1]["triggered"] is False
    assert result[1]["consecutive_readings"] == 2
    assert result[1]["latest_aqi"] == 320.0


@pytest.mark.asyncio
async def test_poll_aqi_all_zones_isolates_zone_failures(monkeypatch):
    async def fake_fetch(zone_cluster_id, station_lat, station_lon):
        _ = station_lat
        _ = station_lon
        if zone_cluster_id == 1:
            raise RuntimeError("synthetic failure")
        return 315.0

    monkeypatch.setattr(aqi_monitor, "fetch_aqi_for_zone", fake_fetch)

    result = await poll_aqi_all_zones([
        {"id": 1, "centroid_lat": 13.0, "centroid_lon": 80.0},
        {"id": 2, "centroid_lat": 13.1, "centroid_lon": 80.1},
    ])

    assert result[1]["triggered"] is False
    assert result[1]["consecutive_readings"] == 0
    assert result[1]["latest_aqi"] is None

    assert result[2]["triggered"] is False
    assert result[2]["consecutive_readings"] == 1
    assert result[2]["latest_aqi"] == 315.0
