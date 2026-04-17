import hashlib
import logging
import re
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.gis import get_flood_tier_for_pincode, get_zone_cluster_for_pincode
from app.core.database import get_db
from app.models.audit import AuditEvent
from app.models.platform_partner import PlatformPartner
from app.models.policy import Policy
from app.models.worker import WorkerProfile

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])
logger = logging.getLogger(__name__)


class AadhaarKYCRequest(BaseModel):
    aadhaar_number: str
    otp: str


class AadhaarKYCResponse(BaseModel):
    verified: bool
    aadhaar_hash: str


class PanKYCRequest(BaseModel):
    pan_number: str


class PanKYCResponse(BaseModel):
    verified: bool
    pan_hash: str


class BankKYCRequest(BaseModel):
    upi_vpa: str


class BankKYCResponse(BaseModel):
    verified: bool
    bank_name: str
    account_type: str


class PlatformVerifyRequest(BaseModel):
    platform: str
    partner_id: str


class PlatformVerifyResponse(BaseModel):
    verified: bool
    partner_name: str


class RegisterWorkerRequest(BaseModel):
    aadhaar_hash: str
    pan_hash: str
    upi_vpa: str
    platform: str
    partner_id: str
    pincode: int
    device_fingerprint: str
    language_preference: str


class RegisterWorkerResponse(BaseModel):
    worker_id: UUID
    policy_id: UUID
    status: str
    weekly_premium_amount: float
    coverage_start: datetime | None
    days_until_eligible: int


def _next_sunday_midnight(now_utc: datetime) -> datetime:
    days_until_sunday = (6 - now_utc.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7
    next_sunday = (now_utc + timedelta(days=days_until_sunday)).date()
    return datetime.combine(next_sunday, time.min, tzinfo=timezone.utc)


@router.post("/kyc/aadhaar", response_model=AadhaarKYCResponse)
def verify_aadhaar(payload: AadhaarKYCRequest) -> AadhaarKYCResponse:
    stripped_aadhaar = payload.aadhaar_number.replace(" ", "")

    if len(stripped_aadhaar) != 12 or not stripped_aadhaar.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aadhaar number must be exactly 12 digits",
        )

    if len(payload.otp) != 6 or not payload.otp.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP must be exactly 6 digits",
        )

    aadhaar_hash = hashlib.sha256(stripped_aadhaar.encode("utf-8")).hexdigest()
    return AadhaarKYCResponse(verified=True, aadhaar_hash=aadhaar_hash)


@router.post("/kyc/pan", response_model=PanKYCResponse)
def verify_pan(payload: PanKYCRequest) -> PanKYCResponse:
    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]{1}", payload.pan_number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PAN number format is invalid",
        )

    pan_hash = hashlib.sha256(payload.pan_number.encode("utf-8")).hexdigest()
    return PanKYCResponse(verified=True, pan_hash=pan_hash)


@router.post("/kyc/bank", response_model=BankKYCResponse)
def verify_bank(payload: BankKYCRequest) -> BankKYCResponse:
    upi_vpa = payload.upi_vpa

    if "@" not in upi_vpa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="UPI VPA must contain '@'",
        )

    if len(upi_vpa) < 5 or len(upi_vpa) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="UPI VPA length must be between 5 and 100 characters",
        )

    return BankKYCResponse(
        verified=True,
        bank_name="HDFC Bank",
        account_type="savings",
    )


@router.post("/platform/verify", response_model=PlatformVerifyResponse)
def verify_platform_partner(
    payload: PlatformVerifyRequest,
    db: Session = Depends(get_db),
) -> PlatformVerifyResponse:
    if payload.platform not in {"zomato", "swiggy"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="platform must be either 'zomato' or 'swiggy'",
        )

    partner = (
        db.query(PlatformPartner)
        .filter_by(platform=payload.platform, partner_id=payload.partner_id)
        .first()
    )

    if partner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partner ID not found for platform",
        )

    return PlatformVerifyResponse(verified=True, partner_name=partner.partner_name)


@router.post("/register", response_model=RegisterWorkerResponse)
def register_worker(
    payload: RegisterWorkerRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RegisterWorkerResponse:
    if payload.platform not in {"zomato", "swiggy"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="platform must be either 'zomato' or 'swiggy'",
        )

    if payload.language_preference not in {"ta", "en"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="language_preference must be either 'ta' or 'en'",
        )

    # Step 1: Duplicate aadhaar_hash check
    existing_aadhaar = db.query(WorkerProfile).filter_by(aadhaar_hash=payload.aadhaar_hash).first()
    if existing_aadhaar is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="aadhaar_hash already registered",
        )

    # Step 2: Duplicate pan_hash check
    existing_pan = db.query(WorkerProfile).filter_by(pan_hash=payload.pan_hash).first()
    if existing_pan is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="pan_hash already registered",
        )

    # Step 3: Duplicate device_fingerprint check (non-blocking)
    existing_fingerprint_worker = None
    if payload.device_fingerprint:
        existing_fingerprint_worker = (
            db.query(WorkerProfile)
            .filter_by(device_fingerprint=payload.device_fingerprint)
            .first()
        )
        if existing_fingerprint_worker is not None:
            db.add(
                AuditEvent(
                    event_type="device_fingerprint_collision",
                    entity_id=existing_fingerprint_worker.id,
                    entity_type="worker",
                    payload={
                        "device_fingerprint": payload.device_fingerprint,
                        "existing_worker_id": str(existing_fingerprint_worker.id),
                    },
                    actor="system",
                )
            )

    # Step 4: Flood tier lookup
    flood_hazard_tier = get_flood_tier_for_pincode(payload.pincode)

    # Step 5: Zone cluster lookup
    zone_cluster_id = get_zone_cluster_for_pincode(payload.pincode)

    existing_partner = (
        db.query(WorkerProfile)
        .filter(
            WorkerProfile.partner_id == payload.partner_id,
            WorkerProfile.platform == payload.platform,
        )
        .first()
    )
    if existing_partner:
        raise HTTPException(
            status_code=409,
            detail="This platform partner ID is already registered",
        )

    # Step 6: Create worker profile
    # WorkerProfile.enrollment_date is the authoritative source for waiting-period
    # and days_until_claim_eligible calculations in policy endpoints.
    now_utc = datetime.now(timezone.utc)
    worker = WorkerProfile(
        aadhaar_hash=payload.aadhaar_hash,
        pan_hash=payload.pan_hash,
        platform=payload.platform,
        partner_id=payload.partner_id,
        pincode=payload.pincode,
        flood_hazard_tier=flood_hazard_tier,
        zone_cluster_id=zone_cluster_id,
        upi_vpa=payload.upi_vpa,
        device_fingerprint=payload.device_fingerprint,
        language_preference=payload.language_preference,
        enrollment_date=now_utc,
        enrollment_week=1,
        is_active=True,
    )
    db.add(worker)
    db.flush()

    # Step 7: Create waiting policy
    next_renewal_at = _next_sunday_midnight(now_utc)
    policy = Policy(
        worker_id=worker.id,
        status="waiting",
        weekly_premium_amount=Decimal("75.00"),
        coverage_week_number=1,
        clean_claim_weeks=0,
        next_renewal_at=next_renewal_at,
    )
    db.add(policy)
    db.flush()

    # Persist worker + policy before calling the premium endpoint from a separate DB session.
    db.commit()
    db.refresh(worker)
    db.refresh(policy)

    # Step 8: Internal premium service call with fallback
    premium_amount = Decimal("75.00")
    model_used = "glm"
    shap_explanation_json = []
    premium_url = f"{str(request.base_url).rstrip('/')}/api/v1/premium/calculate"
    try:
        with httpx.Client(timeout=5.0) as client:
            premium_response = client.post(premium_url, json={"worker_id": str(worker.id)})
        premium_response.raise_for_status()
        premium_payload = premium_response.json()
        premium_amount = Decimal(str(premium_payload.get("premium_amount", "75.00")))
        model_used = premium_payload.get("model_used") or model_used
        shap_explanation_json = premium_payload.get("shap_top3") or []
    except Exception as exc:
        logger.warning("Premium service unavailable during registration: %s", exc)

    policy.weekly_premium_amount = premium_amount
    policy.model_used = model_used
    policy.shap_explanation_json = shap_explanation_json

    # Step 9: Write worker_registered audit event
    db.add(
        AuditEvent(
            event_type="worker_registered",
            entity_id=worker.id,
            entity_type="worker",
            payload={
                "worker_id": str(worker.id),
                "zone_cluster_id": zone_cluster_id,
            },
            actor="system",
        )
    )

    db.commit()
    db.refresh(worker)
    db.refresh(policy)

    # Step 10: Return registration response
    return RegisterWorkerResponse(
        worker_id=worker.id,
        policy_id=policy.id,
        status="waiting",
        weekly_premium_amount=float(policy.weekly_premium_amount),
        coverage_start=None,
        days_until_eligible=28,
    )


class OnboardingStatusResponse(BaseModel):
    worker_id: UUID
    policy_id: UUID
    registration_complete: bool
    policy_status: str
    days_since_enrollment: int
    days_until_claim_eligible: int
    is_coverage_active: bool
    waiting_period_days: int
    enrollment_date: datetime


@router.get("/status/{worker_id}", response_model=OnboardingStatusResponse)
def get_onboarding_status(
    worker_id: UUID,
    db: Session = Depends(get_db),
) -> OnboardingStatusResponse:
    """Return registration and waiting period status for a worker."""
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

    now_utc = datetime.now(timezone.utc)
    enrollment_date = worker.enrollment_date
    if enrollment_date.tzinfo is None:
        enrollment_date = enrollment_date.replace(tzinfo=timezone.utc)

    days_since_enrollment = (now_utc - enrollment_date).days
    waiting_period_days = 28
    days_until_eligible = max(0, waiting_period_days - days_since_enrollment)
    is_coverage_active = (
        policy.status == "active" and days_until_eligible == 0
    )

    return OnboardingStatusResponse(
        worker_id=worker.id,
        policy_id=policy.id,
        registration_complete=True,
        policy_status=policy.status,
        days_since_enrollment=days_since_enrollment,
        days_until_claim_eligible=days_until_eligible,
        is_coverage_active=is_coverage_active,
        waiting_period_days=waiting_period_days,
        enrollment_date=enrollment_date,
    )

