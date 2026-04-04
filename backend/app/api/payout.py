"""Payout API endpoints for worker history and Razorpay webhook updates."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.audit import AuditEvent
from app.models.payout import PayoutEvent
from app.models.worker import WorkerProfile


router = APIRouter(prefix="/api/v1/payout", tags=["payout"])


class PayoutHistoryItem(BaseModel):
    payout_event_id: UUID
    claim_id: UUID
    amount: float
    status: str
    razorpay_payout_id: str | None
    initiated_at: datetime | None
    completed_at: datetime | None


class PayoutHistoryResponse(BaseModel):
    worker_id: UUID
    items: list[PayoutHistoryItem]


class WebhookResponse(BaseModel):
    processed: bool
    payout_id: str
    mapped_status: Literal["paid", "failed", "processing", "initiated"]


def _dt_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _to_uuid(value: Any) -> UUID:
    return cast(UUID, value)


def _to_str_or_none(value: Any) -> str | None:
    typed = cast(str | None, value)
    return typed


def _to_float_any(value: Any) -> float:
    return float(cast(float | int, value))


@router.get("/{worker_id}/history", response_model=PayoutHistoryResponse)
def get_worker_payout_history(worker_id: UUID, db: Session = Depends(get_db)) -> PayoutHistoryResponse:
    worker = db.query(WorkerProfile).filter(WorkerProfile.id == worker_id).first()
    if worker is None:
        raise HTTPException(status_code=404, detail="worker_id not found")

    payouts = (
        db.query(PayoutEvent)
        .filter(PayoutEvent.worker_id == worker_id)
        .order_by(PayoutEvent.initiated_at.desc())
        .all()
    )

    return PayoutHistoryResponse(
        worker_id=worker_id,
        items=[
            PayoutHistoryItem(
                payout_event_id=_to_uuid(p.id),
                claim_id=_to_uuid(p.claim_id),
                amount=_to_float_any(p.amount),
                status=str(p.status),
                razorpay_payout_id=_to_str_or_none(p.razorpay_payout_id),
                initiated_at=_dt_utc(cast(datetime | None, p.initiated_at)),
                completed_at=_dt_utc(cast(datetime | None, p.completed_at)),
            )
            for p in payouts
        ],
    )


@router.post("/webhook/razorpay", response_model=WebhookResponse)
async def razorpay_payout_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None, alias="X-Razorpay-Signature"),
    db: Session = Depends(get_db),
) -> WebhookResponse:
    raw_body = await request.body()

    if not x_razorpay_signature:
        raise HTTPException(status_code=401, detail="missing Razorpay signature")

    expected_signature = hmac.new(
        settings.razorpay_key_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, x_razorpay_signature):
        raise HTTPException(status_code=401, detail="invalid Razorpay signature")

    payload = await request.json()
    event_type = str(payload.get("event", ""))

    payout_entity = payload.get("payload", {}).get("payout", {}).get("entity", {})
    payout_id = payout_entity.get("id")
    if not payout_id:
        raise HTTPException(status_code=422, detail="payout entity id missing in webhook payload")

    payout_event = db.query(PayoutEvent).filter(PayoutEvent.razorpay_payout_id == payout_id).first()
    if payout_event is None:
        raise HTTPException(status_code=404, detail="payout_event not found for payout id")

    mapped_status = "processing"
    if event_type == "payout.processed":
        mapped_status = "paid"
    elif event_type == "payout.failed":
        mapped_status = "failed"

    cast(Any, payout_event).status = mapped_status
    if mapped_status in {"paid", "failed"}:
        cast(Any, payout_event).completed_at = datetime.now(timezone.utc)

    db.add(
        AuditEvent(
            event_type="payout_status_updated",
            entity_id=payout_event.id,
            entity_type="payout_event",
            payload={
                "payout_id": payout_id,
                "webhook_event": event_type,
                "mapped_status": mapped_status,
            },
            actor="system",
        )
    )
    db.commit()

    return WebhookResponse(
        processed=True,
        payout_id=str(payout_id),
        mapped_status=mapped_status,
    )
