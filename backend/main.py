from fastapi import FastAPI, HTTPException, Body, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import os, asyncio
from pathlib import Path
from sqlalchemy import inspect, text
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

# Face recognition was retired: attendance is now recorded through a lecturer
# QR code plus verified classroom location. The optional face-recognition
# dependency is no longer imported or required.

from database import engine, Base, get_db
from models import (
    User, Attendance, FacultySchedule, NEPCourse, SystemSetting, Course,
    CourseEnrolment, Notification, AuditLog, LearningMaterial,
    Faculty, Department, Programme, Venue, AcademicSession, CoursePrerequisite,
    CourseBatch, CourseProgramme, EnrolmentHistory, AttendanceSession,
    AttendanceCorrection, Assessment, Result, ResultAudit, GradingBand, Announcement,
)
from schemas import LoginRequest, StudentSignup
from utils import verify_password, hash_password
from auth import create_access_token, get_current_user
from seed import seed_data, PERIOD_TIMES, ALL_PERIODS
import realtime
from realtime import notify, notify_many, audit, publish_sync

app = FastAPI(title="Smart Campus Attendance API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174"
    ).split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers.admin import router as admin_router
from routers.academic_structure import router as academic_structure_router
from routers.academic import router as academic_router
from routers.realtime_routes import router as realtime_router
from routers.attendance import router as attendance_router
from routers.assessments import router as assessments_router
from routers.registration import router as registration_router
app.include_router(admin_router)
app.include_router(academic_structure_router)
app.include_router(academic_router)
app.include_router(realtime_router)
app.include_router(attendance_router)
app.include_router(assessments_router)
app.include_router(registration_router)

Base.metadata.create_all(bind=engine)

# ── Safe, additive schema migrations (see migrations.py) ──────────────────────
from migrations import run_migrations
run_migrations()

with engine.begin() as conn:
    if "section" in {col["name"] for col in inspect(engine).get_columns("users")}:
        conn.execute(text("UPDATE users SET section = 'AI-1A' WHERE role = 'student' AND section IS NULL"))

seed_data()


@app.on_event("startup")
async def _capture_event_loop():
    # The SSE hub needs the running loop so synchronous route handlers can
    # publish events without blocking on I/O.
    realtime.set_event_loop(asyncio.get_running_loop())


@app.get("/events")
async def events(token: str, db: Session = Depends(get_db)):
    """Server-Sent Events stream for live campus updates.

    Authentication is by query token because the browser EventSource API cannot
    set an Authorization header. The stream is scoped to the token's user.
    """
    from auth import SECRET_KEY, ALGORITHM
    from jose import jwt as _jwt, JWTError as _JWTError
    from fastapi.responses import StreamingResponse

    try:
        payload = _jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
    except _JWTError:
        raise HTTPException(401, "Invalid stream token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(401, "Invalid stream token")
    cid, queue = realtime.register_client(user.id, user.role)
    return StreamingResponse(
        realtime.event_stream(cid, queue),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )

# Location/clock helpers live in geo.py so the attendance router and this module
# share one implementation.
from geo import (  # noqa: E402
    APP_TIMEZONE, DEV_ALLOW_ANY_TIME, GPS_RADIUS_METERS, app_now, haversine, validated_gps,
)


# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"message": "Smart Campus Backend Running", "status": "ok",
            "attendance_mode": "lecturer_qr_selfie_and_verified_location"}


@app.get("/health")
def health():
    """Readiness probe: Render must receive a non-2xx response if DB is down."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": True}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": False},
        )


# ── Login ─────────────────────────────────────────────────────────────────────
@app.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email.ilike(request.email.strip())).first()
    if not user or not verify_password(request.password, user.password):
        raise HTTPException(401, "The email or password is incorrect. Check your details and try again.")
    selected_role = request.selected_role.strip().lower()
    selected_role = "faculty" if selected_role == "lecturer" else selected_role
    if user.role != selected_role:
        raise HTTPException(403, f"This account is registered as {user.role}, not {selected_role}. Choose the correct account type.")
    if user.role in ("student", "faculty") and not user.is_approved:
        raise HTTPException(403, "Administrator approval pending")
    token = create_access_token({"user_id": user.id})
    return {"access_token": token, "role": user.role, "id": user.id,
            "name": user.name, "index_number": user.index_number,
            "department_id": user.department_id, "programme_id": user.programme_id,
            "department": user.department, "programme_name": user.programme_name,
            "institution_name": user.institution_name}


# ── Student Signup ────────────────────────────────────────────────────────────
@app.post("/student/signup")
def student_signup(request: StudentSignup, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    import re
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(422, "Enter a valid email address")
    if db.query(User).filter(User.email.ilike(email)).first():
        raise HTTPException(400, "Email already registered")
    index_number = request.index_number.strip().upper()
    if not index_number:
        raise HTTPException(422, "Index number is required")
    if db.query(User).filter(User.index_number == index_number).first():
        raise HTTPException(409, "Index number already registered")

    programme = db.query(Programme).filter(Programme.id == request.programme_id).first() if request.programme_id else None
    if request.programme_id and not programme:
        raise HTTPException(404, "Select a valid academic programme")
    department = db.query(Department).filter(Department.id == programme.department_id).first() if programme and programme.department_id else None

    approval_setting = db.query(SystemSetting).filter(SystemSetting.key == "auto_approve_students").first()
    auto_approve = bool(approval_setting and approval_setting.value.lower() == "true")
    from storage import save_selfie
    from routers.registration import _clean_identity_document, _ghana_hash
    document_type, document_number = _clean_identity_document(
        request.identity_document_type, request.identity_document_number or request.ghana_card_number
    )
    document_hash = _ghana_hash(document_type + ":" + document_number)
    if db.query(User).filter(User.identity_document_hash == document_hash).first():
        raise HTTPException(409, "This identity document is already associated with an account")
    legacy_ghana_hash = _ghana_hash(document_number) if document_type == "ghana_card" else None
    if legacy_ghana_hash and db.query(User).filter(User.ghana_card_hash == legacy_ghana_hash).first():
        raise HTTPException(409, "This Ghana Card is already associated with an account")
    if not request.consent_biometrics:
        raise HTTPException(422, "Consent is required to collect and process your registration selfie")
    photo_ref = save_selfie(request.registration_selfie)
    db.add(User(
        name=request.name.strip(), index_number=index_number, email=email,
        password=hash_password(request.password),
        role="student", department=(request.department_name.strip() or (department.name if department else None)),
        department_id=programme.department_id if programme else None, programme_id=programme.id if programme else None,
        institution_name=request.institution_name.strip(), faculty_name=(request.faculty_name or "").strip() or None,
        programme_name=request.programme_name.strip(), academic_year=(request.academic_year or "").strip() or None,
        level=request.level or 100, is_approved=auto_approve,
        interests=(request.interests or "").strip(), phone=request.phone.strip(),
        ghana_card_hash=legacy_ghana_hash, ghana_card_last4=document_number[-4:] if document_type == "ghana_card" else None,
        identity_document_type=document_type, identity_document_hash=document_hash, identity_document_last4=document_number[-4:],
        registration_photo_ref=photo_ref, biometric_method=request.biometric_method,
        identity_status="pending",
    ))
    db.commit()
    return {"message": "Signup successful." if auto_approve else "Signup successful. Waiting for admin approval.",
            "status": "approved" if auto_approve else "pending",
            "programme": (programme.name if programme else request.programme_name),
            "department": department.name if department else request.department_name}


# ── Attendance is handled by routers/attendance.py (QR + selfie + GPS) ────────


# ── Admin ─────────────────────────────────────────────────────────────────────
@app.get("/admin/pending-students")
def pending_students(cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if cu.role != "admin": raise HTTPException(403, "Access denied")
    rows = db.query(User).filter(User.role == "student", User.is_approved == False,
                                 User.identity_status == "pending").all()
    out = []
    for s in rows:
        programme = db.query(Programme).filter(Programme.id == s.programme_id).first() if s.programme_id else None
        out.append({"id": s.id, "name": s.name, "email": s.email,
                    "index_number": s.index_number, "phone": s.phone,
                    "institution_name": s.institution_name, "faculty_name": s.faculty_name,
                    "academic_year": s.academic_year,
                    "ghana_card_last4": s.ghana_card_last4, "identity_document_type": s.identity_document_type,\n                    "identity_document_last4": s.identity_document_last4, "identity_status": s.identity_status,
                    "programme_id": s.programme_id,
                    "programme_name": programme.name if programme else s.programme_name,
                    "level": s.level, "department": s.department})
    return out

@app.post("/admin/approve/{student_id}")
def approve_student(student_id: int, cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if cu.role != "admin": raise HTTPException(403, "Access denied")
    s = db.query(User).filter(User.id == student_id, User.role == "student").first()
    if not s: raise HTTPException(404, "Student not found")
    s.is_approved = True
    s.identity_status = "verified"
    db.commit()
    audit(db, cu, "approve", "student", s.id, s.name)
    notify(db, s.id, "Account approved",
           "Your Smart Campus student account has been approved. You can now sign in.",
           category="account", link="/student/dashboard")
    publish_sync("students", {"action": "approve", "id": s.id}, roles=["admin"])
    return {"message": "Approved"}


# ── Generate QR ───────────────────────────────────────────────────────────────
# Kept as a thin wrapper over the attendance-session workflow in
# routers/attendance.py so existing clients keep working. The returned token is
# single-use per session and must be combined with a student selfie + GPS.
@app.post("/faculty/generate-qr/{faculty_id}/{period}")
def generate_qr(
    faculty_id: int, period: str,
    payload: dict = Body(default={}),
    cu: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if cu.role != "faculty" or cu.id != faculty_id:
        raise HTTPException(403, "Only the signed-in lecturer can generate attendance")
    course_id = payload.get("course_id")
    schedule = db.query(FacultySchedule).filter(
        FacultySchedule.faculty_id == faculty_id,
        FacultySchedule.period == period).first()
    if not course_id and schedule:
        course_id = schedule.course_id
    linked_course = db.query(Course).filter(Course.id == course_id, Course.lecturer_id == faculty_id).first() if course_id else None
    if not linked_course:
        raise HTTPException(404, "Select one of your courses to open attendance")
    from routers.attendance import OpenSessionBody, open_session
    body = OpenSessionBody(course_id=linked_course.id,
                           schedule_id=(schedule.id if schedule and schedule.course_id == linked_course.id else None),
                           period=(period if schedule and schedule.course_id == linked_course.id else None),
                           latitude=payload.get("latitude"), longitude=payload.get("longitude"),
                           accuracy=payload.get("accuracy", 30), radius_meters=payload.get("radius_meters"),
                           session_minutes=payload.get("session_minutes"))
    data = open_session(body, cu, db)
    return {"session_id": data["id"], "period": data["period"],
            "subject": data["course_title"], "course_code": data["course_code"],
            "expires_at": data["expires_at"], "has_gps": data["has_gps"], "token": data["token"]}


# ── Faculty Attendance View ────────────────────────────────────────────────────
@app.get("/faculty/attendance/{period}")
def view_attendance(period: str, cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if cu.role != "faculty": raise HTTPException(403, "Access denied")
    today = app_now().date().isoformat()
    schedule = db.query(FacultySchedule).filter(
        FacultySchedule.faculty_id == cu.id,
        FacultySchedule.day_of_week == app_now().weekday(),
        FacultySchedule.period == period
    ).first()
    if not schedule:
        raise HTTPException(404, "No class is assigned to you for this period today")

    # Prefer the day's open attendance session; fall back to a schedule-scoped roster.
    session = db.query(AttendanceSession).filter(
        AttendanceSession.faculty_id == cu.id, AttendanceSession.date == today,
        AttendanceSession.period == period).order_by(AttendanceSession.opened_at.desc()).first()
    if session:
        from routers.attendance import _session_dict
        data = _session_dict(session, db, with_roster=True)
        data["course_code"] = data.get("course_code") or schedule.subject_code
        data["course_title"] = data.get("course_title") or schedule.subject
        return data

    if schedule.course_id:
        students = [s for _, s in db.query(CourseEnrolment, User).join(
            User, CourseEnrolment.student_id == User.id).filter(
            CourseEnrolment.course_id == schedule.course_id,
            CourseEnrolment.status == "approved").all()]
    else:
        students_query = db.query(User).filter(User.role == "student", User.is_approved == True)
        if schedule.section:
            students_query = students_query.filter(User.section == schedule.section)
        students = students_query.all()
    records = db.query(Attendance).filter(
        Attendance.faculty_id == cu.id, Attendance.date == today, Attendance.period == period).all()
    present_ids = {r.student_id: r for r in records}
    return {
        "date": today, "period": period, "course_code": schedule.subject_code,
        "course_title": schedule.subject, "section": schedule.section,
        "present": [{"id": s.id, "name": s.name, "index_number": s.index_number,
                     "marked_by": present_ids[s.id].marked_by,
                     "marked_at": present_ids[s.id].marked_at.isoformat() if present_ids[s.id].marked_at else None}
                    for s in students if s.id in present_ids],
        "absent": [{"id": s.id, "name": s.name, "index_number": s.index_number}
                   for s in students if s.id not in present_ids],
    }


# ── Faculty Timetable ─────────────────────────────────────────────────────────
@app.get("/faculty/timetable/{day}")
def get_timetable(day: int, cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if cu.role != "faculty": raise HTTPException(403, "Access denied")
    scheduled = db.query(FacultySchedule).filter(
        FacultySchedule.faculty_id == cu.id, FacultySchedule.day_of_week == day
    ).all()
    by_period = {s.period: s for s in scheduled}
    result = []
    for p in ALL_PERIODS:
        start, end = PERIOD_TIMES[p]
        s = by_period.get(p)
        if s:
            course = db.query(Course).filter(Course.id == s.course_id).first() if s.course_id else None
            batch = db.query(CourseBatch).filter(CourseBatch.id == s.batch_id).first() if s.batch_id else None
            result.append({"period": p, "subject": s.subject, "subject_code": s.subject_code,
                           "batch_id": s.batch_id, "batch_name": batch.name if batch else None,
                           "class_type": s.class_type, "room_no": s.room_no,
                           "start_time": s.start_time, "end_time": s.end_time, "is_free": False,
                           "course_id": s.course_id, "course_title": course.title if course else s.subject,
                           "is_published": s.is_published})
        else:
            result.append({"period": p, "subject": "Free Period", "subject_code": None,
                           "batch_id": None, "batch_name": None, "class_type": None, "room_no": None,
                           "start_time": start, "end_time": end, "is_free": True})
    return result


# ── Attendance Percentage ─────────────────────────────────────────────────────
@app.get("/student/attendance-percentage")
def attendance_pct(cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if cu.role != "student": raise HTTPException(403, "Access denied")
    # Single source of truth: the same calculation powers the attendance page,
    # so the dashboard percentage and the attendance history never disagree.
    from routers.attendance import student_attendance_summary
    return student_attendance_summary(db, cu)




# ── Signed-in user's editable profile ─────────────────────────────────────────
class MyProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    institution_name: Optional[str] = None
    faculty_name: Optional[str] = None
    department: Optional[str] = None
    programme_name: Optional[str] = None
    academic_year: Optional[str] = None
    designation: Optional[str] = None


@app.get("/profile")
def my_profile(cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    programme = db.query(Programme).filter(Programme.id == cu.programme_id).first() if cu.programme_id else None
    department = db.query(Department).filter(Department.id == cu.department_id).first() if cu.department_id else None
    return {"id": cu.id, "role": cu.role, "name": cu.name, "email": cu.email,
            "phone": cu.phone, "index_number": cu.index_number, "staff_id": cu.staff_id,
            "institution_name": cu.institution_name, "faculty_name": cu.faculty_name,
            "department": department.name if department else cu.department,
            "programme": programme.name if programme else cu.programme_name, "level": cu.level,
            "academic_year": cu.academic_year, "designation": cu.designation,
            "ghana_card_last4": cu.ghana_card_last4,
            "identity_status": cu.identity_status, "is_approved": cu.is_approved}


@app.patch("/profile")
def update_my_profile(body: MyProfileUpdate, cu: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    if body.name is not None:
        if len(body.name.strip()) < 2:
            raise HTTPException(422, "Name must contain at least two characters")
        cu.name = body.name.strip()
    if body.email is not None:
        email = body.email.strip().lower()
        import re
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise HTTPException(422, "Enter a valid email address")
        duplicate = db.query(User).filter(User.email.ilike(email), User.id != cu.id).first()
        if duplicate:
            raise HTTPException(409, "Email already registered")
        cu.email = email
    if body.phone is not None:
        phone = body.phone.strip()
        if len(phone) < 7 or len(phone) > 24:
            raise HTTPException(422, "Enter a valid phone number")
        cu.phone = phone
    previous_institution = cu.institution_name
    for field in ("institution_name", "faculty_name", "department", "programme_name", "academic_year", "designation"):
        value = getattr(body, field)
        if value is not None:
            setattr(cu, field, value.strip() or None)
    if cu.role == "faculty" and body.institution_name is not None and cu.institution_name != previous_institution:
        db.query(Course).filter(Course.lecturer_id == cu.id).update(
            {Course.institution_name: cu.institution_name}, synchronize_session=False)
    if body.department is not None:
        cu.department_id = None
    if body.programme_name is not None:
        cu.programme_id = None
    db.commit()
    return {"message": "Profile updated successfully"}


# ── Shared, relationship-scoped user profiles ─────────────────────────────────
@app.get("/profiles/{profile_user_id}")
def view_user_profile(profile_user_id: int, cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == profile_user_id, User.role.in_(["student", "faculty"])).first()
    if not target:
        raise HTTPException(404, "Profile not found")
    allowed = cu.role == "admin" or cu.id == target.id
    if not allowed and cu.role == "faculty" and target.role == "student":
        allowed = db.query(CourseEnrolment).join(Course, Course.id == CourseEnrolment.course_id).filter(
            Course.lecturer_id == cu.id, CourseEnrolment.student_id == target.id,
            CourseEnrolment.status.in_(["pending", "approved"])).first() is not None
    if not allowed and cu.role == "student" and target.role == "faculty":
        allowed = db.query(CourseEnrolment).join(Course, Course.id == CourseEnrolment.course_id).filter(
            Course.lecturer_id == target.id, CourseEnrolment.student_id == cu.id,
            CourseEnrolment.status == "approved").first() is not None
    if not allowed:
        raise HTTPException(403, "You can only view profiles connected to your approved courses")
    target_programme = db.query(Programme).filter(Programme.id == target.programme_id).first() if target.programme_id else None
    target_department = db.query(Department).filter(Department.id == target.department_id).first() if target.department_id else None
    return {
        "id": target.id, "role": target.role, "name": target.name,
        "email": target.email, "phone": target.phone,
        "institution_name": target.institution_name, "faculty_name": target.faculty_name,
        "department": target_department.name if target_department else target.department,
        "programme_name": target_programme.name if target_programme else target.programme_name,
        "academic_year": target.academic_year, "level": target.level,
        "index_number": target.index_number if target.role == "student" else None,
        "staff_id": target.staff_id if target.role == "faculty" else None,
        "designation": target.designation if target.role == "faculty" else None,
        "identity_status": target.identity_status,
        "ghana_card_last4": target.ghana_card_last4 if cu.role == "admin" else None,
        "has_registration_selfie": bool(target.registration_photo_ref) if cu.role == "admin" else False,
    }


@app.get("/admin/profiles/{profile_user_id}/activity")
def admin_profile_activity(profile_user_id: int, cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Administrative activity summary for one student or lecturer."""
    if cu.role != "admin":
        raise HTTPException(403, "Administrator access required")
    target = db.query(User).filter(User.id == profile_user_id, User.role.in_(["student", "faculty"])).first()
    if not target:
        raise HTTPException(404, "Profile not found")

    if target.role == "student":
        enrolment_rows = db.query(CourseEnrolment, Course, User).join(
            Course, Course.id == CourseEnrolment.course_id).join(
            User, User.id == Course.lecturer_id).filter(
                CourseEnrolment.student_id == target.id).order_by(
                    CourseEnrolment.requested_at.desc()).all()
        enrolments = [{"id": e.id, "course_id": c.id, "course_code": c.code,
                       "course_title": c.title, "lecturer_id": lecturer.id,
                       "lecturer_name": lecturer.name, "status": e.status,
                       "requested_at": e.requested_at.isoformat() if e.requested_at else None}
                      for e, c, lecturer in enrolment_rows]
        attendance_rows = db.query(Attendance, Course).outerjoin(
            Course, Course.id == Attendance.course_id).filter(
                Attendance.student_id == target.id).order_by(
                    Attendance.marked_at.desc()).limit(30).all()
        attendance = [{"id": a.id, "course_code": c.code if c else None,
                       "course_title": c.title if c else None, "date": a.date,
                       "period": a.period, "status": a.status,
                       "marked_at": a.marked_at.isoformat() if a.marked_at else None,
                       "method": a.method} for a, c in attendance_rows]
        present = db.query(Attendance).filter(Attendance.student_id == target.id, Attendance.status == "present").count()
        total = db.query(Attendance).filter(Attendance.student_id == target.id).count()
        return {"user_id": target.id, "role": target.role, "enrolments": enrolments,
                "attendance": attendance, "summary": {"courses": len(enrolments),
                "present": present, "attendance_records": total,
                "attendance_rate": round(present * 100 / total, 1) if total else 0}}

    courses = db.query(Course).filter(Course.lecturer_id == target.id).order_by(Course.code).all()
    course_activity = []
    for course in courses:
        approved = db.query(CourseEnrolment).filter(
            CourseEnrolment.course_id == course.id, CourseEnrolment.status == "approved").count()
        pending = db.query(CourseEnrolment).filter(
            CourseEnrolment.course_id == course.id, CourseEnrolment.status == "pending").count()
        sessions = db.query(AttendanceSession).filter(AttendanceSession.course_id == course.id).count()
        course_activity.append({"course_id": course.id, "course_code": course.code,
                                "course_title": course.title, "approved_students": approved,
                                "pending_requests": pending, "attendance_sessions": sessions})
    recent_sessions = db.query(AttendanceSession, Course).join(
        Course, Course.id == AttendanceSession.course_id).filter(
            AttendanceSession.faculty_id == target.id).order_by(
                AttendanceSession.opened_at.desc()).limit(20).all()
    sessions = [{"id": session.id, "course_code": course.code,
                 "course_title": course.title, "date": session.date,
                 "period": session.period, "is_open": session.is_open,
                 "opened_at": session.opened_at.isoformat() if session.opened_at else None,
                 "present_count": db.query(Attendance).filter(
                     Attendance.attendance_session_id == session.id).count()}
                for session, course in recent_sessions]
    audit_rows = db.query(AuditLog).filter(AuditLog.actor_id == target.id).order_by(
        AuditLog.created_at.desc()).limit(30).all()
    activity_log = [{"id": item.id, "action": item.action, "entity": item.entity,
                     "entity_id": item.entity_id, "detail": item.detail,
                     "created_at": item.created_at.isoformat() if item.created_at else None}
                    for item in audit_rows]
    return {"user_id": target.id, "role": target.role, "courses": course_activity,
            "sessions": sessions, "activity_log": activity_log, "summary": {"courses": len(courses),
            "approved_students": sum(c["approved_students"] for c in course_activity),
            "pending_requests": sum(c["pending_requests"] for c in course_activity),
            "attendance_sessions": sum(c["attendance_sessions"] for c in course_activity)}}


# ── Student Profile ───────────────────────────────────────────────────────────
@app.get("/student/profile")
def get_student_profile(cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if cu.role != "student":
        raise HTTPException(403, "Access denied")
    programme = db.query(Programme).filter(Programme.id == cu.programme_id).first() if cu.programme_id else None
    department = db.query(Department).filter(Department.id == cu.department_id).first() if cu.department_id else None
    session = db.query(AcademicSession).filter(AcademicSession.is_current == True).first()
    return {
        "id":           cu.id,
        "name":         cu.name,
        "email":        cu.email,
        "index_number": cu.index_number,
        "institution_name": cu.institution_name,
        "faculty_name": cu.faculty_name,
        "department":   department.name if department else cu.department,
        "department_name": department.name if department else cu.department,
        "programme_id": cu.programme_id,
        "programme_name": programme.name if programme else cu.programme_name,
        "level":        cu.level,
        "interests":    cu.interests or "",
        "academic_year": cu.academic_year or (session.academic_year if session else None),
        "semester":     session.semester if session else None,
    }


# ── Update own profile (student) ──────────────────────────────────────────────
class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    interests: Optional[str] = None


@app.patch("/student/profile")
def update_student_profile(body: ProfileUpdate, cu: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    if cu.role != "student":
        raise HTTPException(403, "Access denied")
    if body.name is not None and body.name.strip():
        cu.name = body.name.strip()
    if body.interests is not None:
        cu.interests = body.interests.strip()
    db.commit()
    return {"message": "Profile updated"}


# ── Update Interests ──────────────────────────────────────────────────────────
@app.put("/student/update-interests")
def update_interests(
    payload: dict = Body(...),
    cu: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if cu.role != "student":
        raise HTTPException(403, "Access denied")
    interests = (payload.get("interests") or "").strip()
    if not interests:
        raise HTTPException(400, "Interests cannot be empty")
    db.query(User).filter(User.id == cu.id).update({"interests": interests})
    db.commit()
    return {"message": "Interests updated successfully", "interests": interests}


# ── NEP Recommendations — improved scoring ────────────────────────────────────
@app.get("/student/recommendations")
def recommendations(cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if cu.role != "student":
        raise HTTPException(403, "Access denied")

    courses = db.query(NEPCourse).all()
    raw     = (cu.interests or "").lower()

    # Tokenise: split on spaces and commas, drop very short tokens
    interest_words = set(
        w for w in raw.replace(",", " ").split()
        if len(w) > 2
    )

    def score(c):
        tag_words   = set(c.skill_tag.lower().replace(",", " ").replace("-", " ").split())
        title_words = set(c.title.lower().split())
        tag_hits    = sum(2 for w in interest_words if w in tag_words)
        title_hits  = sum(1 for w in interest_words if w in title_words)
        # Partial match bonus (e.g. "ml" inside "machine-learning")
        partial = sum(
            1 for iw in interest_words
            for tw in tag_words
            if tw != iw and len(iw) > 2 and (iw in tw or tw in iw)
        )
        return tag_hits + title_hits + partial

    scored = sorted(courses, key=score, reverse=True)

    return [
        {
            "id":          c.id,
            "title":       c.title,
            "category":    c.category,
            "skill_tag":   c.skill_tag,
            "duration":    c.duration,
            "platform":    c.platform    or "",
            "description": c.description or "",
            "score":       score(c),
        }
        for c in scored
    ]




# ── Admin management read endpoints ───────────────────────────────────────────
def require_admin(cu: User):
    if cu.role != "admin":
        raise HTTPException(403, "Administrator access required")

@app.get("/admin/students")
def admin_students(cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(cu)
    rows = db.query(User).filter(User.role == "student").order_by(User.name).all()
    out = []
    for u in rows:
        programme = db.query(Programme).filter(Programme.id == u.programme_id).first() if u.programme_id else None
        department = db.query(Department).filter(Department.id == u.department_id).first() if u.department_id else None
        out.append({"id": u.id, "name": u.name, "email": u.email, "index_number": u.index_number,
                    "institution_name": u.institution_name, "faculty_name": u.faculty_name,
                    "department": department.name if department else u.department,
                    "department_id": u.department_id,
                    "programme_id": u.programme_id, "programme_name": programme.name if programme else u.programme_name,
                    "academic_year": u.academic_year, "level": u.level, "section": u.section,
                    "interests": u.interests, "identity_status": u.identity_status,
                    "has_registration_selfie": bool(u.registration_photo_ref),
                    "ghana_card_last4": u.ghana_card_last4, "is_approved": u.is_approved})
    return out

@app.get("/admin/faculty")
def admin_faculty(cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(cu)
    return [{"id": u.id, "name": u.name, "email": u.email, "phone": u.phone,
             "staff_id": u.staff_id, "institution_name": u.institution_name,
             "faculty_name": u.faculty_name, "department": u.department,
             "programme_name": u.programme_name, "designation": u.designation,
             "identity_status": u.identity_status,
             "has_registration_selfie": bool(u.registration_photo_ref),
             "ghana_card_last4": u.ghana_card_last4, "is_approved": u.is_approved}
            for u in db.query(User).filter(User.role == "faculty").order_by(User.name).all()]

@app.get("/admin/resources")
def admin_courses(cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(cu)
    return [{"id": c.id, "title": c.title, "category": c.category, "skill_tag": c.skill_tag,
             "duration": c.duration, "platform": c.platform, "description": c.description}
            for c in db.query(NEPCourse).order_by(NEPCourse.title).all()]

@app.get("/admin/attendance-report")
def admin_attendance_report(cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(cu)
    rows = db.query(Attendance, User).join(User, Attendance.student_id == User.id).order_by(Attendance.date.desc()).all()
    out = []
    for a, u in rows:
        course = db.query(Course).filter(Course.id == a.course_id).first() if a.course_id else None
        out.append({"id": a.id, "student_id": a.student_id, "student": u.name, "index_number": u.index_number,
                    "student_email": u.email, "faculty_id": a.faculty_id,
                    "course_id": a.course_id, "course_code": course.code if course else None,
                    "course_title": course.title if course else None,
                    "date": a.date, "period": a.period, "status": a.status, "marked_by": a.marked_by,
                    "timestamp": a.marked_at.isoformat() if a.marked_at else None})
    return out


@app.get("/admin/stats")
def admin_stats_full(cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Expanded analytics for the administrator dashboard."""
    require_admin(cu)
    total_students = db.query(User).filter(User.role == "student").count()
    approved = db.query(User).filter(User.role == "student", User.is_approved == True).count()
    return {
        "total_students": total_students,
        "approved_students": approved,
        "total_faculty": db.query(User).filter(User.role == "faculty").count(),
        "pending_students": total_students - approved,
        "total_courses": db.query(Course).count(),
        "published_courses": db.query(Course).filter(Course.is_published == True).count(),
        "timetable_entries": db.query(FacultySchedule).count(),
        "published_timetable": db.query(FacultySchedule).filter(FacultySchedule.is_published == True).count(),
        "pending_enrolments": db.query(CourseEnrolment).filter(CourseEnrolment.status == "pending").count(),
        "approved_enrolments": db.query(CourseEnrolment).filter(CourseEnrolment.status == "approved").count(),
        "attendance_records": db.query(Attendance).count(),
        "departments": db.query(Department).count(),
        "programmes": db.query(Programme).count(),
        "venues": db.query(Venue).count(),
    }


# ── Debug ─────────────────────────────────────────────────────────────────────
@app.get("/users")
def get_users(cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if cu.role != "admin":
        raise HTTPException(403, "Administrator access required")
    return [{"id": u.id, "name": u.name, "email": u.email,
             "role": u.role, "is_approved": u.is_approved}
            for u in db.query(User).all()]
