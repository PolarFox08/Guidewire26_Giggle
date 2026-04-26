import os
import sys
from decimal import Decimal

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal
from app.models.worker import WorkerProfile
from app.models.zone import ZoneCluster
from app.models.platform_partner import PlatformPartner

def fix_data():
    db = SessionLocal()
    try:
        # 1. Ensure Zones exist
        zones = {
            4: {"name": "Anna Nagar", "lat": 13.0850, "lon": 80.2101, "tier": 2},
            7: {"name": "Velachery", "lat": 12.9816, "lon": 80.2180, "tier": 3},
            9: {"name": "Tambaram", "lat": 12.9249, "lon": 80.1000, "tier": 2},
        }
        
        for zid, data in zones.items():
            existing = db.query(ZoneCluster).filter_by(id=zid).first()
            if not existing:
                db.add(ZoneCluster(
                    id=zid,
                    centroid_lat=Decimal(str(data["lat"])),
                    centroid_lon=Decimal(str(data["lon"])),
                    flood_tier_numeric=data["tier"],
                    avg_heavy_rain_days_yr=Decimal("12.50"),
                    zone_rate_min=Decimal("15.00"),
                    zone_rate_mid=Decimal("18.00"),
                    zone_rate_max=Decimal("25.00"),
                ))
                print(f"Created Zone {zid}")

        db.commit()

        # 2. Update Workers based on exact partner IDs from the frontend
        # Priya (ZMT001)
        priya = db.query(WorkerProfile).filter_by(partner_id="ZMT001").first()
        if priya:
            priya.pincode = 600042
            priya.zone_cluster_id = 7
            priya.language_preference = "ta"
            print("Updated Priya (ZMT001) to Zone 7")

        # Ravi (SWG001)
        ravi = db.query(WorkerProfile).filter_by(partner_id="SWG001").first()
        if ravi:
            ravi.pincode = 600040
            ravi.zone_cluster_id = 4
            ravi.language_preference = "ta"
            print("Updated Ravi (SWG001) to Zone 4")

        # Mohammed (ZMT002)
        mohammed = db.query(WorkerProfile).filter_by(partner_id="ZMT002").first()
        if mohammed:
            mohammed.pincode = 600045
            mohammed.zone_cluster_id = 9
            mohammed.language_preference = "hi"
            print("Updated Mohammed (ZMT002) to Zone 9")

        db.commit()
        print("Successfully updated database records for the 3 demo workers!")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_data()
