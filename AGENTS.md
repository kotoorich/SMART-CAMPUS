# Smart Campus — Attendance Management

## Scope

This is an attendance management system, not an LMS. Main roles are student, lecturer (`faculty` internally) and administrator. Do not surface learning materials, skills, recommendations or assessment modules in the primary navigation.

## Stack

- Frontend: React 19 + Vite, React Router 7, Tailwind, `html5-qrcode`, `qrcode.react`, `react-webcam`.
- Backend: FastAPI + SQLAlchemy 2.0 + Pydantic 2.
- Database: SQLite locally; PostgreSQL in production.

## Core invariants

- `Course` is the canonical course record. Timetable entries, enrolments and attendance sessions reference `Course.id`.
- Students see and join courses using lecturer-issued registration codes; course preview and enrolment eligibility are server-validated.
- Only approved enrolments can mark attendance.
- Smart Campus is independent of any single institution; student and lecturer accounts supply their own institution and academic/professional details. There is no institution-creation or institution-setup workflow.
- Student/lecturer shared profile visibility is relationship-scoped: lecturers see students with pending/approved enrolment requests for their own courses; students see lecturers for their approved courses; administrators see all. Never expose Ghana Card values, passwords or private selfies through shared profile JSON.
- Attendance is session-scoped and unique per student/session. A session has a short-lived QR token and a separate human-enterable access code.
- Attendance requires session validity, enrolment, geofence validation and a newly captured selfie evidence image. Exact byte-for-byte selfie reuse is blocked as an anti-replay check; this is not face recognition or liveness detection.
- Timetable days/times are informational only and must never gate opening or submitting attendance. The lecturer may open a session for any owned course at any time; the session expiry and session-specific GPS radius govern submissions.
- Each attendance session snapshots the lecturer-selected GPS radius and reference location; later platform-default changes must not alter old sessions.
- Registration selfies and attendance photos are private; never serve them from a public static directory.
- Ghana Card values are stored as keyed hashes plus last four characters, never plaintext.
- Paystack payment status must be verified server-side against reference, amount, currency and customer email.
- `registration_fee_required` snapshots whether a lecturer's registration required payment so later policy changes do not alter an existing application.
- Auth tokens live in `sessionStorage` via `frontend/src/utils/session.js`.
- Demo seeding only runs when `SEED_DEMO_DATA=true` and `ENVIRONMENT!=production`.
- `.env` files are gitignored; `.env.example` files are templates.

## Important limitation

Selfies are collected and stored as evidence, but automated face matching/liveness and WebAuthn fingerprint/passkey enrolment are not implemented. Never label selfie capture as facial recognition.

## Commands

Backend (from `backend/`):

```bash
python -m pytest -q
python -m uvicorn main:app --reload
```

Frontend (from `frontend/`):

```bash
npm ci
npm run lint
npm run build
```

## Delivery

Build ZIPs without `node_modules`, `.venv`, `__pycache__`, `dist`, `.git`, `private_uploads`, `*.db`, `.env` and the ZIP itself. Never include private identity/attendance photos or production secrets.
