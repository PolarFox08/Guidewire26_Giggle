import math

import pytest

from app.trigger.open_meteo import (
    get_bearing_offset,
    get_current_precipitation,
    query_three_points,
)


class DummyResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class DummyAsyncClient:
    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params):
        _ = url
        _ = params
        return DummyResponse(
            {
                "hourly": {
                    "precipitation": [1.0] * 24,
                }
            }
        )


def test_get_bearing_offset_known_result_within_tolerance():
    lat, lon = get_bearing_offset(13.0827, 80.2707, 22.5, 3.0)

    assert abs(lat - 13.1076) < 0.01
    assert abs(lon - 80.2813) < 0.01


@pytest.mark.asyncio
async def test_get_current_precipitation_sums_last_24_hours(monkeypatch):
    from app.trigger import open_meteo

    monkeypatch.setattr(open_meteo.httpx, "AsyncClient", DummyAsyncClient)

    precipitation = await get_current_precipitation(13.0827, 80.2707)

    assert precipitation == 24.0


@pytest.mark.asyncio
async def test_query_three_points_returns_max_precipitation(monkeypatch):
    values = [50.0, 80.0, 30.0]

    async def fake_get_current_precipitation(lat: float, lon: float) -> float:
        _ = lat
        _ = lon
        return values.pop(0)

    from app.trigger import open_meteo

    monkeypatch.setattr(open_meteo, "get_current_precipitation", fake_get_current_precipitation)

    result = await query_three_points(13.0827, 80.2707)

    assert result["max_precipitation_24h_mm"] == 80.0
    assert result["successful_points"] == 3
    assert result["degraded"] is False


@pytest.mark.asyncio
async def test_query_three_points_sets_degraded_when_only_one_succeeds(monkeypatch):
    call_counter = {"count": 0}

    async def fake_get_current_precipitation(lat: float, lon: float) -> float:
        _ = lat
        _ = lon
        call_counter["count"] += 1
        if call_counter["count"] == 2:
            return 42.0
        raise ValueError("synthetic failure")

    from app.trigger import open_meteo

    monkeypatch.setattr(open_meteo, "get_current_precipitation", fake_get_current_precipitation)

    result = await query_three_points(13.0827, 80.2707)

    assert result["max_precipitation_24h_mm"] == 42.0
    assert result["successful_points"] == 1
    assert result["degraded"] is True


@pytest.mark.asyncio
async def test_query_three_points_raises_when_all_points_fail(monkeypatch):
    async def fake_get_current_precipitation(lat: float, lon: float) -> float:
        _ = lat
        _ = lon
        raise ValueError("synthetic failure")

    from app.trigger import open_meteo

    monkeypatch.setattr(open_meteo, "get_current_precipitation", fake_get_current_precipitation)

    with pytest.raises(RuntimeError, match="All Open-Meteo point queries failed"):
        await query_three_points(13.0827, 80.2707)
