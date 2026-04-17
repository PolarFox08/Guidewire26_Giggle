import sys
sys.path.insert(0, '.')
import traceback
from app.tasks.trigger_polling import initiate_zone_payouts
from app.core.database import get_db
from app.models.trigger import TriggerEvent

db_gen = get_db()
db = next(db_gen)
t = db.query(TriggerEvent).filter(TriggerEvent.status.in_(['active','recovering'])).first()
if not t:
    # Use any trigger
    t = db.query(TriggerEvent).order_by(TriggerEvent.triggered_at.desc()).first()

if t:
    print('trigger_id:', t.id, type(t.id))
    print('zone:', t.zone_cluster_id)
    try:
        r = initiate_zone_payouts(str(t.id), int(t.zone_cluster_id), 1)
        print('SUCCESS:', r)
    except Exception as e:
        print('FAILED:', e)
        traceback.print_exc()
else:
    print('No trigger found at all')
