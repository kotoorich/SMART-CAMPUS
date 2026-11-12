"""Self-service student/lecturer onboarding and verified lecturer registration payments.

Ghana Card numbers are never stored in plaintext. A keyed HMAC is used for
uniqueness checks and only the final four characters are retained for display.
Registration selfies are stored outside the public web root.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import urllib.error
import urllib.request
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import SECRET_KEY
from database import get_db
from deps import require_admin
from models import User, Department, Faculty, SystemSetting, RegistrationPayment
from storage import save_selfie, resolve_path, delete_selfie
from utils import hash_password

router = APIRouter(tags=["registration"])


def _setting(db: Session, key: str, default: str) -> str:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    return row.value if row else default


def _set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(SystemSetting(key=key, value=value))


def _ghana_hash(value: str) -> str:
    normalized = re.sub(r"\s+", "", value).upper()
    return hmac.new(SECRET_KEY.encode(), normalized.encode(), hashlib.sha256).hexdigest()


def _clean_ghana_card(value: str) -> str:
    normalized = re.sub(r"\s+", "", value).upper()
    if not re.fullmatch(r"GHA-[0-9]{9}-[0-9]", normalized):
        raise HTTPException(422, "Enter a valid Ghana Card number in the format GHA-XXXXXXXXX-X")
    return normalized


def _email_available(db: Session, email: str):
    if db.query(User).filter(User.email.ilike(email)).first():
        raise HTTPException(409, "Email already registered")


class LecturerSignup(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    staff_id: str = Field(min_length=2, max_length=40)
    email: str = Field(min_length=5, max_length=254)
    phone: str = Field(min_length=7, max_length=24)
    password: str = Field(min_length=8, max_length=128)
    department_id: Optional[int] = None
    institution_name: str = Field(min_length=2, max_length=180)
    faculty_name: str = Field(min_length=2, max_length=160)
    department_name: str = Field(min_length=2, max_length=160)
    programme_name: str = Field(min_length=2, max_length=180)
    designation: Optional[str] = Field(default=None, max_length=120)
    identity_document_type: str = Field(default="ghana_card", pattern="^(ghana_card|passport)$")
    identity_document_number: Optional[str] = Field(default=None, min_length=6, max_length=32)
    ghana_card_number: Optional[str] = None
    registration_selfie: str = Field(min_length=100)
    biometric_method: str = Field(default="selfie", pattern="^(selfie|device_biometric)$")
    consent_biometrics: bool = False


class LecturerFeeSettings(BaseModel):
    lecturer_registration_free: bool = False
    lecturer_registration_fee_ghs: float = Field(default=0, ge=0, le=100000)


@router.get("/public/registration-policy")
def public_registration_policy(db: Session = Depends(get_db)):
    free = _setting(db, "lecturer_registration_free", "true").lower() == "true"
    pesewas = int(_setting(db, "lecturer_registration_fee_pesewas", "0"))
    payment_ready = bool(os.getenv("PAYSTACK_SECRET_KEY", "").strip() and os.getenv("PAYSTACK_CALLBACK_URL", "").strip())
    return {"lecturer_registration_free": free,
            "lecturer_registration_fee_ghs": round(pesewas / 100, 2) if not free else 0,
            "payment_provider": "Paystack" if payment_ready else None}


@router.get("/admin/registration-policy")
def get_registration_policy(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return public_registration_policy(db)


@router.put("/admin/registration-policy")
def update_registration_policy(body: LecturerFeeSettings, user: User = Depends(require_admin),
                               db: Session = Depends(get_db)):
    if not body.lecturer_registration_free and body.lecturer_registration_fee_ghs <= 0:
        raise HTTPException(422, "Enter a registration fee greater than zero, or enable free registration")
    _set_setting(db, "lecturer_registration_free", str(body.lecturer_registration_free).lower())
    _set_setting(db, "lecturer_registration_fee_pesewas", str(round(body.lecturer_registration_fee_ghs * 100)))
    db.commit()
    return {"message": "Lecturer registration policy saved", **body.model_dump()}


@router.post("/lecturer/signup", status_code=201)
def lecturer_signup(body: LecturerSignup, db: Session = Depends(get_db)):
    email = str(body.email).strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(422, "Enter a valid email address")
    _email_available(db, email)
    staff_id = body.staff_id.strip().upper()
    if db.query(User).filter(User.staff_id == staff_id).first():
        raise HTTPException(409, "Staff ID already registered")
    document_type, document_number = _clean_identity_document(body.identity_document_type, body.identity_document_number or body.ghana_card_number)
    document_hash = _ghana_hash(document_type + ":" + document_number)
    if db.query(User).filter(User.identity_document_hash == document_hash).first():
        raise HTTPException(409, "This identity document is already associated with an account")
    legacy_ghana_hash = _ghana_hash(document_number) if document_type == "ghana_card" else None
    department = None
    if body.department_id:
        department = db.query(Department).filter(Department.id == body.department_id).first()
        if not department:
            raise HTTPException(404, "Department not found")
    if not body.consent_biometrics:
        raise HTTPException(422, "Consent is required to collect and process your registration selfie")
    photo_ref = save_selfie(body.registration_selfie)
    free = _setting(db, "lecturer_registration_free", "true").lower() == "true"
    amount = int(_setting(db, "lecturer_registration_fee_pesewas", "0"))
    lecturer = User(name=body.name.strip(), email=email, password=hash_password(body.password),
                    role="faculty", department=(body.department_name.strip() or (department.name if department else None)),
                    department_id=department.id if department else None,
                    institution_name=body.institution_name.strip(), faculty_name=(body.faculty_name or "").strip() or None,
                    programme_name=(body.programme_name or "").strip() or None, designation=(body.designation or "").strip() or None,
                    phone=body.phone.strip(), staff_id=staff_id,
                    ghana_card_hash=legacy_ghana_hash, ghana_card_last4=document_number[-4:] if document_type == "ghana_card" else None,
                    identity_document_type=document_type, identity_document_hash=document_hash, identity_document_last4=document_number[-4:],
                    registration_photo_ref=photo_ref, biometric_method=body.biometric_method,
                    identity_status="pending", is_approved=False,
                    registration_fee_required=(not free and amount > 0))
    db.add(lecturer)
    db.flush()

    if free:
        db.commit()
        return {"message": "Registration submitted for administrator verification.",
                "status": "pending_approval", "payment_required": False}

    if amount <= 0:
        db.rollback()
        delete_selfie(photo_ref)
        raise HTTPException(422, "A positive registration fee is required when paid registration is enabled")
    secret = os.getenv("PAYSTACK_SECRET_KEY", "").strip()
    if not secret:
        db.rollback()
        delete_selfie(photo_ref)
        # The account is not created if the configured paid flow cannot be charged.
        raise HTTPException(503, "Lecturer registration is paid, but Paystack is not configured. Contact the administrator.")

    reference = "SC-LECT-" + secrets.token_urlsafe(18).replace("-", "").replace("_", "")
    callback = os.getenv("PAYSTACK_CALLBACK_URL", "").strip()
    if not callback:
        db.rollback()
        delete_selfie(photo_ref)
        raise HTTPException(503, "PAYSTACK_CALLBACK_URL is not configured. Contact the administrator.")
    payload = {"email": email, "amount": amount, "currency": "GHS", "reference": reference, "callback_url": callback}
    request = urllib.request.Request(
        "https://api.paystack.co/transaction/initialize",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            provider_data = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        db.rollback()
        delete_selfie(photo_ref)
        raise HTTPException(502, "Could not initialize payment with Paystack. Please try again.") from exc
    if not provider_data.get("status") or not provider_data.get("data", {}).get("authorization_url"):
        db.rollback()
        delete_selfie(photo_ref)
        raise HTTPException(502, "Payment provider did not return a valid checkout session")
    data = provider_data["data"]
    db.add(RegistrationPayment(user_id=lecturer.id, reference=reference, amount_pesewas=amount,
                               currency="GHS", provider="paystack", status="initialized",
                               authorization_url=data["authorization_url"]))
    db.commit()
    return {"message": "Continue to secure payment to complete lecturer registration.",
            "status": "pending_payment", "payment_required": True,
            "authorization_url": data["authorization_url"], "reference": reference}


@router.get("/lecturer/payment/verify/{reference}")
def verify_lecturer_payment(reference: str, db: Session = Depends(get_db)):
    payment = db.query(RegistrationPayment).filter(RegistrationPayment.reference == reference).first()
    if not payment:
        raise HTTPException(404, "Payment reference not found")
    if payment.status == "paid":
        return {"status": "paid", "message": "Payment already verified. Registration is awaiting administrator approval."}
    secret = os.getenv("PAYSTACK_SECRET_KEY", "").strip()
    if not secret:
        raise HTTPException(503, "Payment verification is not configured")
    request = urllib.request.Request(
        f"https://api.paystack.co/transaction/verify/{reference}",
        headers={"Authorization": f"Bearer {secret}"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise HTTPException(502, "Could not verify payment. Try again shortly.") from exc
    data = result.get("data") or {}
    expected = payment.amount_pesewas
    payment_user = db.query(User).filter(User.id == payment.user_id).first()
    customer_email = ((data.get("customer") or {}).get("email") or "").strip().lower()
    if result.get("status") and data.get("status") == "success" \
            and data.get("reference") == reference \
            and int(data.get("amount", -1)) == expected \
            and data.get("currency") == payment.currency \
            and payment_user is not None and customer_email == payment_user.email.lower():
        payment.status = "paid"
        payment.provider_transaction_id = str(data.get("id") or "")
        payment.verified_at = datetime.utcnow()
        db.commit()
        return {"status": "paid", "message": "Payment verified. Registration is awaiting administrator approval."}
    payment.status = "failed" if data.get("status") in {"failed", "abandoned"} else payment.status
    db.commit()
    return {"status": payment.status, "message": "Payment has not been verified as successful."}


@router.get("/admin/registration-selfies/{user_id}")
def get_registration_selfie(user_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    subject = db.query(User).filter(User.id == user_id, User.role.in_(("student", "faculty"))).first()
    if not subject or not subject.registration_photo_ref:
        raise HTTPException(404, "Registration selfie not found")
    path = resolve_path(subject.registration_photo_ref)
    media = ".jpg" if path.suffix.lower() == ".jpg" else ".png" if path.suffix.lower() == ".png" else ".webp"
    return FileResponse(path, media_type={".jpg":"image/jpeg", ".png":"image/png", ".webp":"image/webp"}[media])


@router.get("/admin/pending-lecturers")
def pending_lecturers(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(User).filter(User.role == "faculty", User.is_approved == False,
                                 User.identity_status == "pending").order_by(User.created_at.desc()).all()
    return [{"id": u.id, "name": u.name, "email": u.email, "staff_id": u.staff_id,
             "phone": u.phone, "institution_name": u.institution_name, "faculty_name": u.faculty_name,
             "department": u.department, "programme_name": u.programme_name,
             "designation": u.designation, "identity_status": u.identity_status,
             "ghana_card_last4": u.ghana_card_last4, "created_at": u.created_at.isoformat() if u.created_at else None}
            for u in rows]


@router.post("/admin/lecturers/{lecturer_id}/approve")
def approve_lecturer(lecturer_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    lecturer = db.query(User).filter(User.id == lecturer_id, User.role == "faculty").first()
    if not lecturer:
        raise HTTPException(404, "Lecturer not found")
    if lecturer.registration_fee_required:
        payment = db.query(RegistrationPayment).filter(RegistrationPayment.user_id == lecturer.id, RegistrationPayment.status == "paid").first()
        if not payment:
            raise HTTPException(409, "Lecturer registration payment has not been verified")
    lecturer.is_approved = True
    lecturer.identity_status = "verified"
    db.commit()
    return {"message": "Lecturer approved", "lecturer_id": lecturer.id}


@router.post("/admin/lecturers/{lecturer_id}/reject")
def reject_lecturer(lecturer_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    lecturer = db.query(User).filter(User.id == lecturer_id, User.role == "faculty").first()
    if not lecturer:
        raise HTTPException(404, "Lecturer not found")
    lecturer.is_approved = False
    lecturer.identity_status = "rejected"
    db.commit()
    return {"message": "Lecturer rejected", "lecturer_id": lecturer.id}


@router.get("/admin/lecturer-payments")
def lecturer_payment_history(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(RegistrationPayment).order_by(RegistrationPayment.created_at.desc()).limit(500).all()
    result = []
    for payment in rows:
        lecturer = db.query(User).filter(User.id == payment.user_id).first()
        result.append({"id": payment.id, "lecturer_name": lecturer.name if lecturer else "Deleted account",
                       "email": lecturer.email if lecturer else None, "reference": payment.reference,
                       "amount_ghs": round(payment.amount_pesewas / 100, 2), "currency": payment.currency,
                       "status": payment.status, "created_at": payment.created_at.isoformat() if payment.created_at else None,
                       "verified_at": payment.verified_at.isoformat() if payment.verified_at else None})
    return result
