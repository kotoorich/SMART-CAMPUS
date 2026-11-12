"""Verify the three local demo accounts against backend/.env without printing secrets."""
from pathlib import Path
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from database import SessionLocal
from models import User
from utils import verify_password


ACCOUNTS = [
    ("Administrator", "DEMO_ADMIN_NAME", "DEMO_ADMIN_EMAIL", "DEMO_ADMIN_PASSWORD", "admin"),
    ("Lecturer", "DEMO_FACULTY_NAME", "DEMO_FACULTY_EMAIL", "DEMO_FACULTY_PASSWORD", "faculty"),
    ("Student", "DEMO_STUDENT_NAME", "DEMO_STUDENT_EMAIL", "DEMO_STUDENT_PASSWORD", "student"),
]


def main() -> int:
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        print("Refusing to verify demo accounts in production.")
        return 2
    if os.getenv("SEED_DEMO_DATA", "false").lower() != "true":
        print("SEED_DEMO_DATA is not true in backend/.env. Local demo accounts are disabled.")
        return 2

    db = SessionLocal()
    failed = False
    try:
        for label, name_key, email_key, password_key, expected_role in ACCOUNTS:
            email = os.getenv(email_key, "").strip().lower()
            password = os.getenv(password_key, "")
            name = os.getenv(name_key, "").strip()
            user = db.query(User).filter(User.email.ilike(email)).first() if email else None
            password_ok = bool(user and password and verify_password(password, user.password))
            identity_ok = bool(user and user.name == name and user.role == expected_role and user.is_approved)
            status = "PASS" if password_ok and identity_ok else "FAIL"
            print(f"{status} {label}: {email or '(email not configured)'} | account={bool(user)} | identity/role/approval={identity_ok} | password={password_ok}")
            failed = failed or status == "FAIL"
    finally:
        db.close()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
