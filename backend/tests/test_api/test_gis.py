import logging

import app.core.gis as gis
from app.core.gis import get_flood_tier_for_pincode


def test_known_chennai_pincode_returns_valid_tier_string():
    tier = get_flood_tier_for_pincode(600020)

    assert tier in {"high", "medium", "low"}


def test_unknown_pincode_returns_low_without_crashing():
    assert get_flood_tier_for_pincode(999999) == "low"


def test_empty_zone_clusters_returns_default_with_warning(monkeypatch, caplog):
    class DummyQuery:
        def all(self):
            return []

    class DummySession:
        def query(self, _model):
            return DummyQuery()

        def close(self):
            return None

    monkeypatch.setattr(gis, "SessionLocal", lambda: DummySession())

    with caplog.at_level(logging.WARNING):
        cluster_id = gis.get_zone_cluster_for_pincode(600020)

    assert cluster_id == 1
    assert (
        "zone_clusters table is empty — returning default cluster 1. Run scripts/zone_clustering.py first."
        in caplog.text
    )
