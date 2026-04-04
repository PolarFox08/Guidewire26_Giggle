"""Claims API endpoints for history, details, pending queue, and resolution."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.audit import AuditEvent
from app.models.claims import Claim
from app.models.payout import PayoutEvent
from app.models.worker import WorkerProfile
from app.payout.razorpay_client import initiate_upi_payout


router = APIRouter(prefix="/api/v1/claims", tags=["claims"])


class ClaimHistoryItem(BaseModel):
    claim_id: UUID
    claim_date: datetime | None
    total_payout_amount: float
    total_paid_amount: float
    fraud_score: float
    fraud_routing: str
    status: str


class ClaimHistoryResponse(BaseModel):
    worker_id: UUID
    items: list[ClaimHistoryItem]


class ClaimDetailResponse(BaseModel):
    claim_id: UUID
    worker_id: UUID
    trigger_event_id: UUID
    policy_id: UUID
    claim_date: datetime | None
    cascade_day: int
    deliveries_completed: int
    base_loss_amount: float
    slab_delta_amount: float
    monthly_proximity_amount: float
    peak_multiplier_applied: bool
    total_payout_amount: float
    fraud_score: float
    fraud_routing: str
    status: str
    zone_claim_match: bool | None
    activity_7d_score: float | None


class PendingClaimItem(BaseModel):
    claim_id: UUID
    worker_id: UUID
    claim_date: datetime | None
    fraud_score: float
    fraud_routing: str
    status: str
    zone_claim_match: bool | None
    activity_7d_score: float | None


class PendingClaimsResponse(BaseModel):
    items: list[PendingClaimItem]


class ResolveClaimRequest(BaseModel):
    resolution: Literal["approve", "reject"]


class ResolveClaimResponse(BaseModel):
    claim_id: UUID
    status: str
    paid_before: float
    total_payout_amount: float
    remaining_payout_attempted: float
    payout_triggered: bool


def _dt_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _as_float(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _to_uuid(value: Any) -> UUID:
    return cast(UUID, value)


def _to_str(value: Any) -> str:
    return str(cast(str, value))


def _to_int(value: Any) -> int:
    return int(cast(int, value))


def _to_float_any(value: Any) -> float:
    return _as_float(cast(Decimal | float | int | None, value))


def _to_bool_or_none(value: Any) -> bool | None:
    return cast(bool | None, value)


@router.get("/detail/{claim_id}", response_model=ClaimDetailResponse)
def get_claim_detail(
    claim_id: UUID,
    db: Session = Depends(get_db),
) -> ClaimDetailResponse:
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if claim is None:
        raise HTTPException(status_code=404, detail="claim_id not found")

    return ClaimDetailResponse(
        claim_id=_to_uuid(claim.id),
        worker_id=_to_uuid(claim.worker_id),
        trigger_event_id=_to_uuid(claim.trigger_event_id),
        policy_id=_to_uuid(claim.policy_id),
        claim_date=_dt_utc(cast(datetime | None, claim.claim_date)),
        cascade_day=_to_int(claim.cascade_day),
        deliveries_completed=_to_int(claim.deliveries_completed),
        base_loss_amount=_to_float_any(claim.base_loss_amount),
        slab_delta_amount=_to_float_any(claim.slab_delta_amount),
        monthly_proximity_amount=_to_float_any(claim.monthly_proximity_amount),
        peak_multiplier_applied=bool(cast(bool, claim.peak_multiplier_applied)),
        total_payout_amount=_to_float_any(claim.total_payout_amount),
        fraud_score=_to_float_any(claim.fraud_score),
        fraud_routing=_to_str(claim.fraud_routing),
        status=_to_str(claim.status),
        zone_claim_match=_to_bool_or_none(claim.zone_claim_match),
        activity_7d_score=(
            None
            if cast(Any, claim.activity_7d_score) is None
            else _to_float_any(claim.activity_7d_score)
        ),
    )


@router.get("/pending", response_model=PendingClaimsResponse)
def get_pending_claims(db: Session = Depends(get_db)) -> PendingClaimsResponse:
    claims = (
        db.query(Claim)
        .filter((Claim.fraud_routing == "partial_review") | (Claim.status == "held"))
        .order_by(desc(Claim.fraud_score))
        .all()
    )

    items = [
        PendingClaimItem(
            claim_id=_to_uuid(claim.id),
            worker_id=_to_uuid(claim.worker_id),
            claim_date=_dt_utc(cast(datetime | None, claim.claim_date)),
            fraud_score=_to_float_any(claim.fraud_score),
            fraud_routing=_to_str(claim.fraud_routing),
            status=_to_str(claim.status),
            zone_claim_match=_to_bool_or_none(claim.zone_claim_match),
            activity_7d_score=(
                None
                if cast(Any, claim.activity_7d_score) is None
                else _to_float_any(claim.activity_7d_score)
            ),
        )
        for claim in claims
    ]
    return PendingClaimsResponse(items=items)


@router.get("/{worker_id}", response_model=ClaimHistoryResponse)
def get_worker_claim_history(
    worker_id: UUID,
    db: Session = Depends(get_db),
) -> ClaimHistoryResponse:
    worker = db.query(WorkerProfile).filter(WorkerProfile.id == worker_id).first()
    if worker is None:
        raise HTTPException(status_code=404, detail="worker_id not found")

    claims = (
        db.query(Claim)
        .filter(Claim.worker_id == worker_id)
        .order_by(Claim.claim_date.desc())
        .all()
    )

    items: list[ClaimHistoryItem] = []
    for claim in claims:
        paid = (
            db.query(func.coalesce(func.sum(PayoutEvent.amount), 0))
            .filter(PayoutEvent.claim_id == claim.id)
            .scalar()
        )
        items.append(
            ClaimHistoryItem(
                claim_id=_to_uuid(claim.id),
                claim_date=_dt_utc(cast(datetime | None, claim.claim_date)),
                total_payout_amount=_to_float_any(claim.total_payout_amount),
                total_paid_amount=_as_float(paid),
                fraud_score=_to_float_any(claim.fraud_score),
                fraud_routing=_to_str(claim.fraud_routing),
                status=_to_str(claim.status),
            )
        )

    return ClaimHistoryResponse(worker_id=worker_id, items=items)


@router.put("/{claim_id}/resolve", response_model=ResolveClaimResponse)
def resolve_claim(
    claim_id: UUID = Path(...),
    payload: ResolveClaimRequest | None = None,
    db: Session = Depends(get_db),
) -> ResolveClaimResponse:
    if payload is None:
        raise HTTPException(status_code=422, detail="resolution is required")

    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if claim is None:
        raise HTTPException(status_code=404, detail="claim_id not found")

    worker = db.query(WorkerProfile).filter(WorkerProfile.id == claim.worker_id).first()
    if worker is None:
        raise HTTPException(status_code=404, detail="worker for claim not found")

    paid_before = (
        db.query(func.coalesce(func.sum(PayoutEvent.amount), 0))
        .filter(PayoutEvent.claim_id == claim.id)
        .scalar()
    )
    paid_before_value = _as_float(paid_before)
    total_payout = _to_float_any(claim.total_payout_amount)

    payout_triggered = False
    remaining = max(0.0, round(total_payout - paid_before_value, 2))

    if payload.resolution == "reject":
        cast(Any, claim).status = "rejected"
        db.add(
            AuditEvent(
                event_type="claim_resolved",
                entity_id=claim.id,
                entity_type="claim",
                payload={"resolution": "reject", "paid_before": paid_before_value},
                actor="admin",
            )
        )
        db.commit()
        return ResolveClaimResponse(
            claim_id=_to_uuid(claim.id),
            status=_to_str(claim.status),
            paid_before=paid_before_value,
            total_payout_amount=total_payout,
            remaining_payout_attempted=0.0,
            payout_triggered=False,
        )

    cast(Any, claim).status = "approved"
    attempted = 0.0

    if remaining > 0:
        attempted = remaining
        result = initiate_upi_payout(_to_str(worker.upi_vpa), remaining, str(claim.id))
        payout_triggered = True

        payout_event = PayoutEvent(
            claim_id=claim.id,
            worker_id=claim.worker_id,
            razorpay_payout_id=result.get("payout_id"),
            amount=Decimal(str(round(remaining, 2))),
            upi_vpa=worker.upi_vpa,
            status=(result.get("status", "processing") if result.get("success") else "failed"),
            failure_reason=(None if result.get("success") else result.get("error")),
        )
        db.add(payout_event)

    db.add(
        AuditEvent(
            event_type="claim_resolved",
            entity_id=claim.id,
            entity_type="claim",
            payload={
                "resolution": "approve",
                "paid_before": paid_before_value,
                "remaining": attempted,
            },
            actor="admin",
        )
    )
    db.commit()

    return ResolveClaimResponse(
        claim_id=_to_uuid(claim.id),
        status=_to_str(claim.status),
        paid_before=paid_before_value,
        total_payout_amount=total_payout,
        remaining_payout_attempted=attempted,
        payout_triggered=payout_triggered,
    )
