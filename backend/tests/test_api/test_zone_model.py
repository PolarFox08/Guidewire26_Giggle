from sqlalchemy import Integer, Numeric

from app.models.zone import ZoneCluster


def test_zone_cluster_table_name():
    assert ZoneCluster.__tablename__ == "zone_clusters"


def test_zone_cluster_schema():
    columns = ZoneCluster.__table__.columns

    assert isinstance(columns["id"].type, Integer)
    assert columns["id"].primary_key is True
    assert isinstance(columns["centroid_lat"].type, Numeric)
    assert columns["centroid_lat"].type.precision == 10
    assert columns["centroid_lat"].type.scale == 7
    assert isinstance(columns["centroid_lon"].type, Numeric)
    assert columns["centroid_lon"].type.precision == 10
    assert columns["centroid_lon"].type.scale == 7
    assert isinstance(columns["flood_tier_numeric"].type, Integer)
    assert isinstance(columns["avg_heavy_rain_days_yr"].type, Numeric)
    assert columns["avg_heavy_rain_days_yr"].type.precision == 5
    assert columns["avg_heavy_rain_days_yr"].type.scale == 2
    assert isinstance(columns["zone_rate_min"].type, Numeric)
    assert columns["zone_rate_min"].type.precision == 6
    assert columns["zone_rate_min"].type.scale == 2
    assert isinstance(columns["zone_rate_mid"].type, Numeric)
    assert columns["zone_rate_mid"].type.precision == 6
    assert columns["zone_rate_mid"].type.scale == 2
    assert isinstance(columns["zone_rate_max"].type, Numeric)
    assert columns["zone_rate_max"].type.precision == 6
    assert columns["zone_rate_max"].type.scale == 2