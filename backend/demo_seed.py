"""
demo_seed.py — Giggle Demo Data Seeder
=========================================
Run this ONCE before recording the demo video.
It creates a realistic Priya worker profile, delivery history,
and puts her policy in 'active' state past the waiting period.

Usage:
    cd backend
    python demo_seed.py

After running, the script prints:
  - worker_id   (use in /docs to query claims, policy, fraud)
  - zone cluster (use in /trigger/simulate)
  - ADMIN_KEY   (use in admin endpoints)
"""

from __future__ import annotations

import hashlib
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

# ── Make sure backend/ is on the Python path ──────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

# Load .env explicitly BEFORE importing any app module (settings reads .env at import time)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)
except ImportError:
    pass  # dotenv not installed — rely on environment variables

os.environ.setdefault("DATABASE_URL", "")  # loaded from .env via settings

from app.core.database import SessionLocal  # noqa: E402
from app.models.audit import AuditEvent  # noqa: E402
from app.models.delivery import DeliveryHistory  # noqa: E402
from app.models.platform_partner import PlatformPartner  # noqa: E402
from app.models.policy import Policy  # noqa: E402
from app.models.worker import WorkerProfile  # noqa: E402
from app.models.zone import ZoneCluster  # noqa: E402

ADMIN_KEY = "gigshield-admin-2026"

# ── Demo worker profile ────────────────────────────────────────────────────────
DEMO_AADHAAR = "999988887777"
DEMO_PAN = "ABCDE1234F"
DEMO_UPI = "priya.demo@upi"
DEMO_PARTNER_ID = "ZMT-DEMO-001"
DEMO_PINCODE = 600042  # Velachery, Chennai — high flood risk zone


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def seed_platform_partner(db) -> None:
    """Ensure the demo partner ID exists in platform_partners."""
    try:
        existing = db.query(PlatformPartner).filter_by(partner_id=DEMO_PARTNER_ID).first()
        if existing:
            return
        db.add(PlatformPartner(
            platform="zomato",
            partner_id=DEMO_PARTNER_ID,
            partner_name="Priya Demo Partner",
        ))
        db.commit()
        print(f"  [OK] Created platform partner: {DEMO_PARTNER_ID}")
    except Exception as e:
        db.rollback()
        print(f"  ! Warning: Platform partner seed skipped/failed: {e}")


def find_or_create_zone(db) -> int:
    """Find first available zone cluster, or create a sensible default."""
    zone = db.query(ZoneCluster).order_by(ZoneCluster.id).first()
    if zone:
        return int(zone.id)

    # No zones yet — create a minimal demo zone for Velachery
    demo_zone = ZoneCluster(
        id=1,
        centroid_lat=Decimal("12.9816"),
        centroid_lon=Decimal("80.2180"),
        flood_tier_numeric=3,           # high
        avg_heavy_rain_days_yr=Decimal("12.50"),
        zone_rate_min=Decimal("15.00"),
        zone_rate_mid=Decimal("18.00"),
        zone_rate_max=Decimal("25.00"),
    )
    db.add(demo_zone)
    db.commit()
    print("  [OK] Created demo zone cluster (id=1, Velachery high-flood)")
    return 1


def seed_worker(db, zone_cluster_id: int) -> WorkerProfile:
    """Create or return the demo worker (Priya)."""
    aadhaar_hash = sha256(DEMO_AADHAAR)
    existing = db.query(WorkerProfile).filter_by(aadhaar_hash=aadhaar_hash).first()
    if existing:
        print(f"  [OK] Demo worker already exists: {existing.id}")
        return existing

    # Enrollment date 30 days ago — past the 28-day waiting period
    enrollment_date = datetime.now(timezone.utc) - timedelta(days=30)

    worker = WorkerProfile(
        aadhaar_hash=aadhaar_hash,
        pan_hash=sha256(DEMO_PAN),
        platform="zomato",
        partner_id=DEMO_PARTNER_ID,
        pincode=DEMO_PINCODE,
        flood_hazard_tier="high",
        zone_cluster_id=zone_cluster_id,
        upi_vpa=DEMO_UPI,
        device_fingerprint="demo-device-fingerprint-priya-001",
        registration_ip="127.0.0.1",
        enrollment_date=enrollment_date,
        enrollment_week=5,             # week 5 → LightGBM M2 takes over
        is_active=True,
        language_preference="ta",
    )
    db.add(worker)
    db.flush()

    db.add(AuditEvent(
        event_type="worker_registered",
        entity_id=worker.id,
        entity_type="worker",
        payload={"worker_id": str(worker.id), "demo_seed": True},
        actor="demo_seed",
    ))
    db.commit()
    print(f"  [OK] Created demo worker (Priya): {worker.id}")
    return worker


def seed_policy(db, worker: WorkerProfile) -> Policy:
    """Create or ensure the demo worker has an ACTIVE policy."""
    existing = db.query(Policy).filter_by(worker_id=worker.id).first()
    if existing:
        if existing.status != "active":
            existing.status = "active"
            existing.coverage_start_date = worker.enrollment_date
            db.commit()
            print(f"  [OK] Policy activated: {existing.id}")
        else:
            print(f"  [OK] Policy already active: {existing.id}")
        return existing

    policy = Policy(
        worker_id=worker.id,
        status="active",
        weekly_premium_amount=Decimal("82.00"),
        coverage_start_date=worker.enrollment_date,
        coverage_week_number=5,
        clean_claim_weeks=4,
        next_renewal_at=datetime.now(timezone.utc) + timedelta(days=3),
        model_used="lgbm",
        shap_explanation_json=[
            "உங்கள் மண்டலத்தில் மழை முன்னறிவிப்பு (+₹12)",
            "வெள்ள அபாய மண்டலம் (+₹8)",
            "5 வார சுத்தமான பதிவு (-₹5)",
        ],
    )
    db.add(policy)
    db.commit()
    print(f"  [OK] Created active policy: {policy.id}")
    return policy


def seed_delivery_history(db, worker: WorkerProfile, zone_cluster_id: int) -> None:
    """Seed 30 days of realistic delivery history for Priya.

    Velachery coordinates: lat=12.9816, lon=80.2180
    Average 14 deliveries/day × 6 days/week.
    """
    existing_count = db.query(DeliveryHistory).filter_by(worker_id=worker.id).count()
    if existing_count > 0:
        print(f"  [OK] Delivery history already exists ({existing_count} records)")
        return

    # Velachery GPS region — slightly vary per record for realism
    BASE_LAT = 12.9816
    BASE_LON = 80.2180

    import random
    random.seed(42)

    records_added = 0
    now = datetime.now(timezone.utc)

    for day_offset in range(30):
        record_date = now - timedelta(days=day_offset)

        # Skip one day/week (Sunday rest)
        if record_date.weekday() == 6:
            continue

        # Morning slot
        morning_deliveries = random.randint(5, 8)
        m_lat = str(round(BASE_LAT + random.uniform(-0.005, 0.005), 7))
        m_lon = str(round(BASE_LON + random.uniform(-0.005, 0.005), 7))
        m_point = f"SRID=4326;POINT({m_lon} {m_lat})"
        db.add(DeliveryHistory(
            worker_id=worker.id,
            recorded_at=record_date.replace(hour=10, minute=0, second=0),
            deliveries_count=morning_deliveries,
            earnings_declared=Decimal(str(round(morning_deliveries * 18.5, 2))),
            gps_latitude=m_point,
            gps_longitude=m_point,
            platform="zomato",
            is_simulated=True,
        ))

        # Evening slot
        evening_deliveries = random.randint(6, 9)
        e_lat = str(round(BASE_LAT + random.uniform(-0.005, 0.005), 7))
        e_lon = str(round(BASE_LON + random.uniform(-0.005, 0.005), 7))
        e_point = f"SRID=4326;POINT({e_lon} {e_lat})"
        db.add(DeliveryHistory(
            worker_id=worker.id,
            recorded_at=record_date.replace(hour=19, minute=0, second=0),
            deliveries_count=evening_deliveries,
            earnings_declared=Decimal(str(round(evening_deliveries * 19.0, 2))),
            gps_latitude=e_point,
            gps_longitude=e_point,
            platform="zomato",
            is_simulated=True,
        ))
        records_added += 2

    db.commit()
    print(f"  [OK] Seeded {records_added} delivery history records (30 days, Velachery GPS)")


def seed_extra_workers(db, zone_cluster_id: int) -> list[dict]:
    """Seed 3 additional workers with distinct fraud risk profiles."""
    import random
    random.seed(99)

    extras = [
        {
            "name": "Rajan",
            "aadhaar": "888877776666",
            "pan": "BCDEF2345G",
            "upi": "rajan.swiggy@upi",
            "partner_id": "SWG-DEMO-002",
            "platform": "swiggy",
            "pincode": 600041,
            "flood_tier": "medium",
            "premium": Decimal("68.00"),
            "enrollment_days_ago": 45,
            "week": 7,
            "device": "demo-device-rajan-002",
            "description": "Rajan (Swiggy, Adyar — medium flood risk)",
        },
        {
            "name": "Kavitha",
            "aadhaar": "777766665555",
            "pan": "CDEFG3456H",
            "upi": "kavitha.v@upi",
            "partner_id": "ZMT-DEMO-003",
            "platform": "zomato",
            "pincode": 600020,
            "flood_tier": "low",
            "premium": Decimal("54.00"),
            "enrollment_days_ago": 62,
            "week": 9,
            "device": "demo-device-kavitha-003",
            "description": "Kavitha (Zomato, T.Nagar — low flood risk)",
        },
        {
            "name": "Muthu",
            "aadhaar": "666655554444",
            "pan": "DEFGH4567I",
            "upi": "muthu.raj@upi",
            "partner_id": "ZMT-DEMO-004",
            "platform": "zomato",
            "pincode": 600042,
            "flood_tier": "high",
            "premium": Decimal("89.00"),
            "enrollment_days_ago": 29,   # Just past waiting period
            "week": 5,
            "device": "demo-device-muthu-004",
            "description": "Muthu (Zomato, Velachery — high risk, new enrollee)",
        },
    ]

    created = []
    for w in extras:
        aadhaar_hash = sha256(w["aadhaar"])
        existing = db.query(WorkerProfile).filter_by(aadhaar_hash=aadhaar_hash).first()
        if existing:
            print(f"  [OK] {w['description']} already exists: {existing.id}")
            # Ensure policy
            pol = db.query(Policy).filter_by(worker_id=existing.id).first()
            created.append({"worker": existing, "policy": pol, **w})
            continue

        # Ensure partner exists
        if not db.query(PlatformPartner).filter_by(partner_id=w["partner_id"]).first():
            db.add(PlatformPartner(
                platform=w["platform"],
                partner_id=w["partner_id"],
                partner_name=f"{w['name']} Demo Partner",
            ))
            db.commit()

        enrollment_date = datetime.now(timezone.utc) - timedelta(days=w["enrollment_days_ago"])
        worker = WorkerProfile(
            aadhaar_hash=aadhaar_hash,
            pan_hash=sha256(w["pan"]),
            platform=w["platform"],
            partner_id=w["partner_id"],
            pincode=w["pincode"],
            flood_hazard_tier=w["flood_tier"],
            zone_cluster_id=zone_cluster_id,
            upi_vpa=w["upi"],
            device_fingerprint=w["device"],
            registration_ip="127.0.0.1",
            enrollment_date=enrollment_date,
            enrollment_week=w["week"],
            is_active=True,
            language_preference="ta",
        )
        db.add(worker)
        db.flush()

        policy = Policy(
            worker_id=worker.id,
            status="active",
            weekly_premium_amount=w["premium"],
            coverage_start_date=enrollment_date,
            coverage_week_number=w["week"],
            clean_claim_weeks=w["week"] - 1,
            next_renewal_at=datetime.now(timezone.utc) + timedelta(days=3),
            model_used="lgbm",
        )
        db.add(policy)

        # Delivery history (shorter, 14 days)
        BASE_LAT = 12.9816 + random.uniform(-0.02, 0.02)
        BASE_LON = 80.2180 + random.uniform(-0.02, 0.02)
        now = datetime.now(timezone.utc)
        for day_offset in range(14):
            record_date = now - timedelta(days=day_offset)
            if record_date.weekday() == 6:
                continue
            deliveries = random.randint(4, 9)
            lat = str(round(BASE_LAT + random.uniform(-0.004, 0.004), 7))
            lon = str(round(BASE_LON + random.uniform(-0.004, 0.004), 7))
            pt = f"SRID=4326;POINT({lon} {lat})"
            db.add(DeliveryHistory(
                worker_id=worker.id,
                recorded_at=record_date.replace(hour=11, minute=0, second=0),
                deliveries_count=deliveries,
                earnings_declared=Decimal(str(round(deliveries * 18.0, 2))),
                gps_latitude=pt,
                gps_longitude=pt,
                platform=w["platform"],
                is_simulated=True,
            ))

        db.commit()
        print(f"  [OK] Created {w['description']}: {worker.id}")
        created.append({"worker": worker, "policy": policy, **w})

    return created


def main() -> None:
    print("\n" + "=" * 60)
    print("  GIGGLE PLATFORM SEED")
    print("=" * 60)

    # ── Ensure tables exist ──────────────────────────────────────────────────
    from app.core.database import DeclarativeBase, engine
    import app.models.audit, app.models.claims, app.models.delivery  # noqa: F401
    import app.models.payout, app.models.platform_partner, app.models.policy  # noqa: F401
    import app.models.trigger, app.models.worker, app.models.zone  # noqa: F401

    print("\n[0/5] Initializing database schema...")
    DeclarativeBase.metadata.create_all(bind=engine)
    print("      [OK] Schema ready")

    db = SessionLocal()
    try:
        print("\n[1/5] Ensuring platform partner...")
        seed_platform_partner(db)

        print("\n[2/5] Finding/creating zone cluster...")
        zone_cluster_id = find_or_create_zone(db)
        print(f"      Zone cluster ID: {zone_cluster_id}")

        print("\n[3/5] Creating primary worker (Priya, Velachery)...")
        worker = seed_worker(db, zone_cluster_id)

        print("\n[4/5] Setting up policy and delivery history...")
        policy = seed_policy(db, worker)
        seed_delivery_history(db, worker, zone_cluster_id)

        print("\n[5/5] Seeding additional workers...")
        seed_extra_workers(db, zone_cluster_id)

    finally:
        db.close()

    print("\n" + "=" * 60)
    print("  PLATFORM SEEDED")
    print("=" * 60)
    print(f"  Primary Worker ID  : {worker.id}")
    print(f"  Zone Cluster       : {zone_cluster_id}")
    print(f"  UPI VPA            : {DEMO_UPI}")
    print(f"  Admin Key          : {ADMIN_KEY}")
    print(f"  Policy ID          : {policy.id}")
    print()


if __name__ == "__main__":
    main()
