from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.fraud.behavioral import (
    check_rain_paradox,
    compute_activity_7d_score,
    compute_enrollment_recency_score,
)
from app.fraud.graph import detect_ring_registrations
from app.fraud.scorer import compute_fraud_score, route_claim
from app.models.claims import Claim
from app.models.delivery import DeliveryHistory
from app.models.worker import WorkerProfile
from app.models.zone import ZoneCluster

router = APIRouter(prefix="/api/v1/fraud", tags=["fraud"])


class FraudScoreRequest(BaseModel):
    worker_id: UUID
    zone_claim_match: int
    claim_to_enrollment_days: int
    event_claim_frequency: int


class FraudScoreResponse(BaseModel):
    fraud_score: float
    routing: str
    signal_breakdown: dict


class FraudQueueItem(BaseModel):
    worker_id: UUID
    claim_date: datetime
    fraud_score: float
    fraud_routing: str
    zone_claim_match: bool | None
    activity_7d_score: float | None
    status: str


class WorkerFraudSignalsResponse(BaseModel):
    total_claim_count: int
    avg_fraud_score: float
    zone_claim_match_history: list[bool | None]
    enrollment_recency_score: float
    ring_registration_flag: bool


@router.post("/score", response_model=FraudScoreResponse)
def score_claim_fraud(payload: FraudScoreRequest, db: Session = Depends(get_db)) -> FraudScoreResponse:
    if payload.zone_claim_match not in {0, 1}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="zone_claim_match must be 0 or 1",
        )

    worker = db.query(WorkerProfile).filter_by(id=payload.worker_id).first()
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker not found",
        )

    now_utc = datetime.now(timezone.utc)
    seven_days_ago = now_utc - timedelta(days=7)
    thirty_days_ago = now_utc - timedelta(days=30)

    worker_delivery_rows = (
        db.query(DeliveryHistory)
        .filter_by(worker_id=payload.worker_id)
        .all()
    )

    deliveries_7d = sum(
        int(row.deliveries_count or 0)
        for row in worker_delivery_rows
        if row.recorded_at and row.recorded_at >= seven_days_ago
    )

    deliveries_30d = sum(
        int(row.deliveries_count or 0)
        for row in worker_delivery_rows
        if row.recorded_at and row.recorded_at >= thirty_days_ago
    )
    avg_daily_30d = deliveries_30d / 30.0

    activity_7d_score = compute_activity_7d_score(
        deliveries_7d=deliveries_7d,
        avg_daily_30d=avg_daily_30d,
    )

    fraud_score = compute_fraud_score(
        zone_claim_match=payload.zone_claim_match,
        activity_7d_score=activity_7d_score,
        claim_to_enrollment_days=payload.claim_to_enrollment_days,
        event_claim_frequency=payload.event_claim_frequency,
    )
    routing = route_claim(fraud_score)

    zone_order_volume_ratio = 1.0
    zone_cluster = db.query(ZoneCluster).filter_by(id=worker.zone_cluster_id).first()
    if zone_cluster is not None:
        raw_ratio = getattr(zone_cluster, "zone_order_volume_ratio", None)
        if isinstance(raw_ratio, (int, float)) and raw_ratio > 0:
            zone_order_volume_ratio = float(raw_ratio)

    rain_paradox_active = check_rain_paradox(
        zone_flood_tier=worker.flood_hazard_tier,
        zone_order_volume_ratio=zone_order_volume_ratio,
    )
    enrollment_recency_score = compute_enrollment_recency_score(worker.enrollment_week)

    signal_breakdown = {
        "zone_claim_match": payload.zone_claim_match,
        "activity_7d_score": activity_7d_score,
        "enrollment_recency_score": enrollment_recency_score,
        "rain_paradox_active": rain_paradox_active,
        "claim_to_enrollment_days": payload.claim_to_enrollment_days,
        "event_claim_frequency": payload.event_claim_frequency,
    }

    return FraudScoreResponse(
        fraud_score=fraud_score,
        routing=routing,
        signal_breakdown=signal_breakdown,
    )


@router.get("/queue", response_model=list[FraudQueueItem])
def get_fraud_queue(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
) -> list[FraudQueueItem]:
    if not x_admin_key or x_admin_key != settings.admin_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    queued_claims = [
        claim
        for claim in db.query(Claim).all()
        if claim.status == "held" or claim.fraud_routing == "partial_review"
    ]
    queued_claims.sort(
        key=lambda claim: claim.claim_date or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    return [
        FraudQueueItem(
            worker_id=claim.worker_id,
            claim_date=claim.claim_date,
            fraud_score=float(claim.fraud_score),
            fraud_routing=claim.fraud_routing,
            zone_claim_match=claim.zone_claim_match,
            activity_7d_score=(
                float(claim.activity_7d_score)
                if claim.activity_7d_score is not None
                else None
            ),
            status=claim.status,
        )
        for claim in queued_claims
    ]


@router.get("/worker/{worker_id}/signals", response_model=WorkerFraudSignalsResponse)
def get_worker_fraud_signals(worker_id: UUID, db: Session = Depends(get_db)) -> WorkerFraudSignalsResponse:
    worker = db.query(WorkerProfile).filter_by(id=worker_id).first()
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker not found",
        )

    worker_claims = [
        claim
        for claim in db.query(Claim).filter_by(worker_id=worker_id).all()
    ]
    worker_claims.sort(
        key=lambda claim: claim.claim_date or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    total_claim_count = len(worker_claims)
    avg_fraud_score = 0.0
    if total_claim_count > 0:
        avg_fraud_score = float(
            sum(float(claim.fraud_score) for claim in worker_claims) / total_claim_count
        )

    zone_claim_match_history = [
        claim.zone_claim_match
        for claim in worker_claims[:10]
    ]
    enrollment_recency_score = compute_enrollment_recency_score(worker.enrollment_week)

    suspected_rings = detect_ring_registrations(db)
    worker_id_str = str(worker.id)
    ring_registration_flag = any(
        worker_id_str in component
        for component in suspected_rings
    )

    return WorkerFraudSignalsResponse(
        total_claim_count=total_claim_count,
        avg_fraud_score=avg_fraud_score,
        zone_claim_match_history=zone_claim_match_history,
        enrollment_recency_score=enrollment_recency_score,
        ring_registration_flag=ring_registration_flag,
    )
