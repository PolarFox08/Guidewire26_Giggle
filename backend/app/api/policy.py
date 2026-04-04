from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.models.audit import AuditEvent
from app.models.policy import Policy
from app.models.worker import WorkerProfile

router = APIRouter(prefix="/api/v1/policy", tags=["policy"])


class PolicyDetailsResponse(BaseModel):
    policy_id: UUID
    status: str
    weekly_premium_amount: float
    coverage_start_date: datetime | None
    coverage_week_number: int
    enrollment_week: int
    model_used: str | None
    shap_explanation_json: list | dict | None
    days_until_claim_eligible: int


class PolicyCoverageResponse(BaseModel):
    is_coverage_active: bool
    current_week_number: int
    weekly_premium_amount: float
    shap_top3: list[str]
    next_renewal_at: datetime | None


def _compute_days_until_claim_eligible(enrollment_date: datetime) -> int:
    enrollment_utc = enrollment_date
    if enrollment_utc.tzinfo is None:
        enrollment_utc = enrollment_utc.replace(tzinfo=timezone.utc)

    days_since_enrollment = (datetime.now(timezone.utc) - enrollment_utc).days
    return max(0, 28 - days_since_enrollment)


def _format_shap_top3(shap_explanation_json: list | dict | None, language: str) -> list[str]:
    items: list[dict] = []

    if isinstance(shap_explanation_json, list):
        for value in shap_explanation_json:
            if isinstance(value, dict):
                items.append(value)
    elif isinstance(shap_explanation_json, dict):
        if isinstance(shap_explanation_json.get("top3"), list):
            for value in shap_explanation_json["top3"]:
                if isinstance(value, dict):
                    items.append(value)

    formatted: list[str] = []
    for item in items[:3]:
        feature = str(item.get("feature", "unknown_feature"))
        direction = str(item.get("direction", "neutral"))
        if language == "ta":
            formatted.append(f"{feature}: {direction} பாதிக்கிறது")
        else:
            formatted.append(f"{feature}: {direction} impact")

    return formatted


@router.get("/{worker_id}", response_model=PolicyDetailsResponse)
def get_policy_details(worker_id: UUID, db: Session = Depends(get_db)) -> PolicyDetailsResponse:
    worker = db.query(WorkerProfile).filter_by(id=worker_id).first()
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker not found",
        )

    policy = db.query(Policy).filter_by(worker_id=worker_id).first()
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found for worker",
        )

    days_until_claim_eligible = _compute_days_until_claim_eligible(worker.enrollment_date)

    return PolicyDetailsResponse(
        policy_id=policy.id,
        status=policy.status,
        weekly_premium_amount=float(policy.weekly_premium_amount),
        coverage_start_date=policy.coverage_start_date,
        coverage_week_number=policy.coverage_week_number,
        enrollment_week=worker.enrollment_week,
        model_used=policy.model_used,
        shap_explanation_json=policy.shap_explanation_json,
        days_until_claim_eligible=days_until_claim_eligible,
    )


@router.get("/{worker_id}/coverage", response_model=PolicyCoverageResponse)
def get_policy_coverage(worker_id: UUID, db: Session = Depends(get_db)) -> PolicyCoverageResponse:
    worker = db.query(WorkerProfile).filter_by(id=worker_id).first()
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker not found",
        )

    policy = db.query(Policy).filter_by(worker_id=worker_id).first()
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found for worker",
        )

    days_until_claim_eligible = _compute_days_until_claim_eligible(worker.enrollment_date)
    is_coverage_active = policy.status == "active" and days_until_claim_eligible == 0
    shap_top3 = _format_shap_top3(policy.shap_explanation_json, worker.language_preference)

    return PolicyCoverageResponse(
        is_coverage_active=is_coverage_active,
        current_week_number=policy.coverage_week_number,
        weekly_premium_amount=float(policy.weekly_premium_amount),
        shap_top3=shap_top3,
        next_renewal_at=policy.next_renewal_at,
    )


@router.put("/{worker_id}/suspend", response_model=PolicyDetailsResponse)
def suspend_policy(
    worker_id: UUID,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
) -> PolicyDetailsResponse:
    if not x_admin_key or x_admin_key != settings.admin_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    worker = db.query(WorkerProfile).filter_by(id=worker_id).first()
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker not found",
        )

    policy = db.query(Policy).filter_by(worker_id=worker_id).first()
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found for worker",
        )

    policy.status = "suspended"

    db.add(
        AuditEvent(
            event_type="policy_suspended",
            entity_id=worker.id,
            entity_type="worker",
            payload={"worker_id": str(worker.id), "reason": "admin_action"},
            actor="system",
        )
    )
    db.commit()

    days_until_claim_eligible = _compute_days_until_claim_eligible(worker.enrollment_date)

    return PolicyDetailsResponse(
        policy_id=policy.id,
        status=policy.status,
        weekly_premium_amount=float(policy.weekly_premium_amount),
        coverage_start_date=policy.coverage_start_date,
        coverage_week_number=policy.coverage_week_number,
        enrollment_week=worker.enrollment_week,
        model_used=policy.model_used,
        shap_explanation_json=policy.shap_explanation_json,
        days_until_claim_eligible=days_until_claim_eligible,
    )
