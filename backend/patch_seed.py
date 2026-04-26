import os
import re

with open("demo_seed.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace the single DEMO variables with a list
new_data_str = """
DEMO_WORKERS = [
    {
        "name": "Priya S.",
        "aadhaar": "999988887777",
        "pan": "ABCDE1234F",
        "upi": "priya.demo@upi",
        "partner_id": "ZMT001",
        "platform": "zomato",
        "pincode": 600042,
        "zone_id": 7,  # Velachery
        "lang": "ta",
        "tier": "high",
        "lat": 12.9816,
        "lon": 80.2180,
        "enrollment_days_ago": 30,
        "week": 5
    },
    {
        "name": "Ravi K.",
        "aadhaar": "888877776666",
        "pan": "BCDEF2345G",
        "upi": "ravi.k@upi",
        "partner_id": "SWG001",
        "platform": "swiggy",
        "pincode": 600040,
        "zone_id": 4,  # Anna Nagar
        "lang": "ta",
        "tier": "medium",
        "lat": 13.0850,
        "lon": 80.2101,
        "enrollment_days_ago": 45,
        "week": 7
    },
    {
        "name": "Mohammed A.",
        "aadhaar": "777766665555",
        "pan": "CDEFG3456H",
        "upi": "mohammed.a@upi",
        "partner_id": "ZMT002",
        "platform": "zomato",
        "pincode": 600045,
        "zone_id": 9,  # Tambaram
        "lang": "hi",
        "tier": "medium",
        "lat": 12.9249,
        "lon": 80.1000,
        "enrollment_days_ago": 62,
        "week": 9
    }
]
"""

content = re.sub(
    r"DEMO_AADHAAR =.*?DEMO_PINCODE = 600042.*?\n",
    new_data_str,
    content,
    flags=re.DOTALL
)

# Update find_or_create_zone
new_zone_func = """def ensure_zones(db) -> None:
    \"\"\"Ensure the specific zones needed for demo workers exist.\"\"\"
    required_zones = {
        4: {"name": "Anna Nagar", "tier": 2, "lat": 13.0850, "lon": 80.2101},
        7: {"name": "Velachery", "tier": 3, "lat": 12.9816, "lon": 80.2180},
        9: {"name": "Tambaram", "tier": 2, "lat": 12.9249, "lon": 80.1000},
    }
    for zid, data in required_zones.items():
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
            print(f"  [OK] Created zone {zid} ({data['name']})")
    db.commit()"""

content = re.sub(
    r"def find_or_create_zone.*?return 1",
    new_zone_func,
    content,
    flags=re.DOTALL
)

# Replace seed_worker
new_seed_worker = """def seed_worker(db, data: dict) -> WorkerProfile:
    \"\"\"Create or return a demo worker.\"\"\"
    aadhaar_hash = sha256(data["aadhaar"])
    existing = db.query(WorkerProfile).filter_by(aadhaar_hash=aadhaar_hash).first()
    if existing:
        print(f"  [OK] Demo worker already exists: {existing.id}")
        return existing

    enrollment_date = datetime.now(timezone.utc) - timedelta(days=data["enrollment_days_ago"])

    # Ensure partner exists
    if not db.query(PlatformPartner).filter_by(partner_id=data["partner_id"]).first():
        db.add(PlatformPartner(
            platform=data["platform"],
            partner_id=data["partner_id"],
            partner_name=f"{data['name']} Partner",
        ))
        db.commit()

    worker = WorkerProfile(
        aadhaar_hash=aadhaar_hash,
        pan_hash=sha256(data["pan"]),
        platform=data["platform"],
        partner_id=data["partner_id"],
        pincode=data["pincode"],
        flood_hazard_tier=data["tier"],
        zone_cluster_id=data["zone_id"],
        upi_vpa=data["upi"],
        device_fingerprint=f"demo-device-{data['name'].replace(' ', '-').lower()}",
        registration_ip="127.0.0.1",
        enrollment_date=enrollment_date,
        enrollment_week=data["week"],
        is_active=True,
        language_preference=data["lang"],
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
    print(f"  [OK] Created demo worker ({data['name']}): {worker.id}")
    return worker"""

content = re.sub(
    r"def seed_worker\(db.*?return worker",
    new_seed_worker,
    content,
    flags=re.DOTALL
)

# Fix seed_policy
new_seed_policy = """def seed_policy(db, worker: WorkerProfile, data: dict) -> Policy:
    \"\"\"Create or ensure the demo worker has an ACTIVE policy.\"\"\"
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
        coverage_week_number=data["week"],
        clean_claim_weeks=data["week"] - 1,
        next_renewal_at=datetime.now(timezone.utc) + timedelta(days=3),
        model_used="lgbm",
        shap_explanation_json=[
            "உங்கள் மண்டலத்தில் மழை முன்னறிவிப்பு (+₹12)" if data["lang"] == "ta" else "आपके क्षेत्र में बारिश का पूर्वानुमान (+₹12)",
            "வெள்ள அபாய மண்டலம் (+₹8)" if data["lang"] == "ta" else "बाढ़ जोखिम क्षेत्र (+₹8)",
            "5 வார சுத்தமான பதிவு (-₹5)" if data["lang"] == "ta" else "5 सप्ताह का स्वच्छ रिकॉर्ड (-₹5)",
        ],
    )
    db.add(policy)
    db.commit()
    print(f"  [OK] Created active policy: {policy.id}")
    return policy"""

content = re.sub(
    r"def seed_policy\(db.*?return policy",
    new_seed_policy,
    content,
    flags=re.DOTALL
)

# Fix seed_delivery_history
new_seed_delivery = """def seed_delivery_history(db, worker: WorkerProfile, data: dict) -> None:
    \"\"\"Seed 30 days of realistic delivery history.\"\"\"
    existing_count = db.query(DeliveryHistory).filter_by(worker_id=worker.id).count()
    if existing_count > 0:
        print(f"  [OK] Delivery history already exists ({existing_count} records)")
        return

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
        m_lat = str(round(data["lat"] + random.uniform(-0.005, 0.005), 7))
        m_lon = str(round(data["lon"] + random.uniform(-0.005, 0.005), 7))
        m_point = f"SRID=4326;POINT({m_lon} {m_lat})"
        db.add(DeliveryHistory(
            worker_id=worker.id,
            recorded_at=record_date.replace(hour=10, minute=0, second=0),
            deliveries_count=morning_deliveries,
            earnings_declared=Decimal(str(round(morning_deliveries * 18.5, 2))),
            gps_latitude=m_point,
            gps_longitude=m_point,
            platform=data["platform"],
            is_simulated=True,
        ))

        # Evening slot
        evening_deliveries = random.randint(6, 9)
        e_lat = str(round(data["lat"] + random.uniform(-0.005, 0.005), 7))
        e_lon = str(round(data["lon"] + random.uniform(-0.005, 0.005), 7))
        e_point = f"SRID=4326;POINT({e_lon} {e_lat})"
        db.add(DeliveryHistory(
            worker_id=worker.id,
            recorded_at=record_date.replace(hour=19, minute=0, second=0),
            deliveries_count=evening_deliveries,
            earnings_declared=Decimal(str(round(evening_deliveries * 19.0, 2))),
            gps_latitude=e_point,
            gps_longitude=e_point,
            platform=data["platform"],
            is_simulated=True,
        ))
        records_added += 2

    db.commit()
    print(f"  [OK] Seeded {records_added} delivery history records")"""

content = re.sub(
    r"def seed_delivery_history\(db.*?print\(f\"  \[OK\] Seeded \{records_added\} delivery history records \(30 days, Velachery GPS\)\"\)",
    new_seed_delivery,
    content,
    flags=re.DOTALL
)

# Remove the old seed_platform_partner and seed_extra_workers
content = re.sub(r"def seed_platform_partner\(db\).*?print\(f\"  ! Warning: Platform partner seed skipped/failed: \{e\}\"\)", "", content, flags=re.DOTALL)
content = re.sub(r"def seed_extra_workers\(db.*?return created", "", content, flags=re.DOTALL)

# Update main
new_main = """def main() -> None:
    print("\\n" + "=" * 60)
    print("  GIGGLE PLATFORM SEED")
    print("=" * 60)

    from app.core.database import DeclarativeBase, engine
    import app.models.audit, app.models.claims, app.models.delivery  # noqa: F401
    import app.models.payout, app.models.platform_partner, app.models.policy  # noqa: F401
    import app.models.trigger, app.models.worker, app.models.zone  # noqa: F401

    print("\\n[0/4] Initializing database schema...")
    DeclarativeBase.metadata.create_all(bind=engine)
    print("      [OK] Schema ready")

    db = SessionLocal()
    try:
        print("\\n[1/4] Ensuring Zones...")
        ensure_zones(db)

        print("\\n[2/4] Creating Workers...")
        for w_data in DEMO_WORKERS:
            worker = seed_worker(db, w_data)
            seed_policy(db, worker, w_data)
            seed_delivery_history(db, worker, w_data)

        print("\\n[3/4] Commit & Verification...")
        db.commit()
        
    finally:
        db.close()

    print("\\n" + "=" * 60)
    print("  PLATFORM SEEDED")
    print("=" * 60)
    print(f"  Admin Key          : {ADMIN_KEY}")
    print()"""

content = re.sub(r"def main\(\) -> None:.*?print\(\)", new_main, content, flags=re.DOTALL)

with open("demo_seed.py", "w", encoding="utf-8") as f:
    f.write(content)
