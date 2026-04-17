"""Quick payout test route — call /api/v1/debug/payout-test to see the full traceback."""
from fastapi import APIRouter
import traceback

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])

@router.get("/payout-test")
def payout_test():
    import sys
    sys.path.insert(0, '.')
    from app.tasks.trigger_polling import initiate_zone_payouts
    from app.core.database import get_db
    from app.models.trigger import TriggerEvent

    db_gen = get_db()
    db = next(db_gen)
    t = db.query(TriggerEvent).order_by(TriggerEvent.triggered_at.desc()).first()
    if not t:
        return {"error": "no trigger found"}
    try:
        r = initiate_zone_payouts(str(t.id), int(t.zone_cluster_id), 1)
        return {"success": True, "result": r}
    except Exception as e:
        tb = traceback.format_exc()
        return {"success": False, "error": str(e), "traceback": tb}
