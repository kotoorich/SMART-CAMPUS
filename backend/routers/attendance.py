"""Attendance: lecturer QR sessions with student selfie + verified location.

A lecturer opens a session for one of their scheduled classes (course → batch →
period). The session carries a signed, single-use QR token, the classroom GPS
position, a permitted radius and an expiry. A student marks attendance by
scanning the QR (or uploading its image) and submitting a live selfie; the
backend then verifies the token, the expiry, the GPS proximity, the student's
approved enrolment for the course/batch, and prevents duplicates.

Attendance photographs are stored privately (see ``storage.py``) and can only be
retrieved through an authenticated endpoint by the owning lecturer or an
administrator.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
from secrets import token_urlsafe, token_hex
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from deps import require_admin, require_roles
from geo import (DEV_ALLOW_ANY_TIME, GPS_ACCURACY_CEILING, GPS_RADIUS_METERS,
                 GPS_SESSION_ACCURACY_CEILING, app_now, haversine, validated_gps)
from models import (
    User, Course, CourseBatch, CourseEnrolment, FacultySchedule, Attendance,
    AttendanceSession, AttendanceCorrection, SystemSetting, AcademicSession,
)
from realtime import audit, notify, publish_sync
from storage import resolve_path, save_selfie
from utils import natural_key

router = APIRouter()

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


# ── helpers ──────────────────────────────────────────────────────────────────
def _session_minutes(db: Session) -> int:
    row = db.query(SystemSetting).filter(SystemSetting.key == "attendance_session_minutes").first()
    return int(row.value) if row and row.value.isdigit() else 10


def _radius(db: Session) -> int:
    row = db.query(SystemSetting).filter(SystemSetting.key == "attendance_gps_radius_meters").first()
    return int(row.value) if row and row.value.isdigit() else GPS_RADIUS_METERS


def _current_session(db: Session) -> Optional[AcademicSession]:
    return db.query(AcademicSession).filter(AcademicSession.is_current == True).first()


def _session_dict(s: AttendanceSession, db: Session, with_roster: bool = False):
    course = db.query(Course).filter(Course.id == s.course_id).first()
    batch = db.query(CourseBatch).filter(CourseBatch.id == s.batch_id).first() if s.batch_id else None
    lecturer = db.query(User).filter(User.id == s.faculty_id).first()
    data = {
        "id": s.id, "course_id": s.course_id, "course_code": course.code if course else None,
        "course_title": course.title if course else None,
        "batch_id": s.batch_id, "batch_name": batch.name if batch else None,
        "faculty_id": s.faculty_id, "faculty_name": lecturer.name if lecturer else None,
        "date": s.date, "period": s.period, "topic": s.topic,
        "access_code": s.access_code,
        "is_open": s.is_open,
        "opened_at": s.opened_at.isoformat() if s.opened_at else None,
        "closed_at": s.closed_at.isoformat() if s.closed_at else None,
        "expires_at": s.expires_at.isoformat() if s.expires_at else None,
        "has_gps": s.latitude is not None and s.longitude is not None,
        "radius_meters": s.radius_meters,
        "present_count": db.query(Attendance).filter(
            Attendance.attendance_session_id == s.id).count(),
    }
    if with_roster:
        data.update(_roster(s, db))
    return data


def _roster(s: AttendanceSession, db: Session):
    """Approved students for the session's course/batch, split present/absent."""
    q = db.query(CourseEnrolment, User).join(
        User, CourseEnrolment.student_id == User.id).filter(
        CourseEnrolment.course_id == s.course_id,
        CourseEnrolment.status == "approved")
    if s.batch_id:
        q = q.filter(CourseEnrolment.batch_id == s.batch_id)
    roster = [(e, u) for e, u in q.all()]
    roster.sort(key=lambda pair: natural_key(pair[1].index_number))
    records = {a.student_id: a for a in db.query(Attendance).filter(
        Attendance.attendance_session_id == s.id).all()}
    present, absent = [], []
    for _e, u in roster:
        rec = records.get(u.id)
        entry = {"id": u.id, "name": u.name, "index_number": u.index_number, "email": u.email,
                 "institution_name": u.institution_name, "faculty_name": u.faculty_name,
                 "department": u.department, "programme_name": u.programme_name, "level": u.level}
        # Expose the underlying record id whenever one exists so a lecturer can
        # correct a record in either direction (present↔absent), not only a
        # present one.
        if rec:
            entry["attendance_id"] = rec.id
        if rec and rec.status == "present":
            entry.update({"marked_at": rec.marked_at.isoformat() if rec.marked_at else None,
                          "method": rec.method, "has_photo": bool(rec.image_ref),
                          "distance_meters": rec.distance_meters, "gps_accuracy": rec.gps_accuracy,
                          "attendance_points": rec.attendance_points})
            present.append(entry)
        else:
            absent.append(entry)
    return {"present": present, "absent": absent}


def _held_sessions_for_student(db: Session, user: User):
    """Sessions a student was eligible to attend, grouped by course.

    A "class held" is a lecturer-opened attendance session for a course the
    student has an approved enrolment in and, when the session targets a batch,
    the student's own batch.
    """
    enrolments = db.query(CourseEnrolment).filter(
        CourseEnrolment.student_id == user.id,
        CourseEnrolment.status == "approved").all()
    by_course = {e.course_id: e for e in enrolments}
    held: dict[int, list] = {}
    if by_course:
        sessions = db.query(AttendanceSession).filter(
            AttendanceSession.course_id.in_(list(by_course.keys()))).all()
        for s in sessions:
            if s.batch_id and by_course[s.course_id].batch_id != s.batch_id:
                continue
            held.setdefault(s.course_id, []).append(s)
    return held


def student_attendance_summary(db: Session, user: User) -> dict:
    """Attendance rate based on classes held, shared by every student surface."""
    held = _held_sessions_for_student(db, user)
    present_session_ids = {a.attendance_session_id for a in db.query(Attendance).filter(
        Attendance.student_id == user.id, Attendance.status == "present",
        Attendance.attendance_session_id.isnot(None)).all()}
    total = sum(len(v) for v in held.values())
    present = sum(1 for v in held.values() for s in v if s.id in present_session_ids)
    # Count legacy present records that predate session linking so the rate
    # never understates attendance.
    present += db.query(Attendance).filter(
        Attendance.student_id == user.id, Attendance.status == "present",
        Attendance.attendance_session_id.is_(None)).count()
    denominator = max(total, present)
    return {"total_classes": total, "present_classes": present,
            "percentage": round((present / denominator) * 100, 2) if denominator else 0}


def _own_schedule(db: Session, user: User, course_id: int, period: Optional[str],
                  schedule_id: Optional[int]):
    """Optionally resolve one of the lecturer's own timetable entries."""
    today = app_now().date()
    weekday = today.weekday()
    if schedule_id:
        row = db.query(FacultySchedule).filter(FacultySchedule.id == schedule_id).first()
        if not row or row.faculty_id != user.id or row.course_id != course_id:
            raise HTTPException(403, "That scheduled class does not belong to you")
        return row
    q = db.query(FacultySchedule).filter(
        FacultySchedule.faculty_id == user.id,
        FacultySchedule.course_id == course_id,
        FacultySchedule.day_of_week == weekday)
    if period:
        q = q.filter(FacultySchedule.period == period)
    return q.first()


# ── Lecturer: session setup ──────────────────────────────────────────────────
@router.get("/admin/attendance/records")
def admin_attendance_records(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    rows = db.query(Attendance).order_by(Attendance.marked_at.desc()).limit(1000).all()
    result = []
    for rec in rows:
        student = db.query(User).filter(User.id == rec.student_id).first()
        lecturer = db.query(User).filter(User.id == rec.faculty_id).first()
        course = db.query(Course).filter(Course.id == rec.course_id).first() if rec.course_id else None
        session = db.query(AttendanceSession).filter(AttendanceSession.id == rec.attendance_session_id).first() if rec.attendance_session_id else None
        result.append({
            "id": rec.id, "student_id": rec.student_id, "student_name": student.name if student else "Deleted student",
            "index_number": student.index_number if student else None,
            "lecturer_id": rec.faculty_id, "lecturer_name": lecturer.name if lecturer else "Deleted lecturer",
            "course_code": course.code if course else None, "course_title": course.title if course else None,
            "date": rec.date, "period": rec.period, "status": rec.status,
            "marked_at": rec.marked_at.isoformat() if rec.marked_at else None,
            "distance_meters": rec.distance_meters, "gps_accuracy": rec.gps_accuracy,
            "radius_meters": session.radius_meters if session else None,
            "has_photo": bool(rec.image_ref),
        })
    return result


@router.get("/faculty/attendance/courses")
def my_attendance_courses(user: User = Depends(require_roles("faculty")), db: Session = Depends(get_db)):
    """Courses assigned to the lecturer, with their optional timetable entries."""
    courses = db.query(Course).filter(Course.lecturer_id == user.id).order_by(Course.code).all()
    out = []
    for c in courses:
        batches = [{"id": b.id, "name": b.name, "capacity": b.capacity,
                    "enrolled_count": db.query(CourseEnrolment).filter(
                        CourseEnrolment.batch_id == b.id,
                        CourseEnrolment.status == "approved").count()}
                   for b in db.query(CourseBatch).filter(
                       CourseBatch.course_id == c.id, CourseBatch.is_active == True).all()]
        schedules = [{"id": s.id, "period": s.period, "batch_id": s.batch_id,
                      "day_of_week": s.day_of_week, "start_time": s.start_time, "end_time": s.end_time,
                      "room_no": s.room_no, "is_published": s.is_published}
                     for s in db.query(FacultySchedule).filter(
                         FacultySchedule.faculty_id == user.id,
                         FacultySchedule.course_id == c.id).order_by(
                             FacultySchedule.day_of_week, FacultySchedule.start_time).all()]
        out.append({"course_id": c.id, "code": c.code, "title": c.title,
                    "level": c.level, "batches": batches, "schedules": schedules})
    return out


class OpenSessionBody(BaseModel):
    course_id: int
    batch_id: Optional[int] = None
    schedule_id: Optional[int] = None
    period: Optional[str] = None
    topic: Optional[str] = None
    latitude: float
    longitude: float
    accuracy: float = 30
    radius_meters: Optional[int] = Field(default=None, ge=10, le=500)
    session_minutes: Optional[int] = Field(default=None, ge=1, le=240)


@router.post("/faculty/attendance/sessions", status_code=201)
def open_session(body: OpenSessionBody, user: User = Depends(require_roles("faculty")),
                 db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == body.course_id).first()
    if not course:
        raise HTTPException(404, "Course not found")
    if course.lecturer_id != user.id:
        raise HTTPException(403, "You can only open attendance for your own courses")

    batch = None
    if body.batch_id is not None:
        batch = db.query(CourseBatch).filter(CourseBatch.id == body.batch_id).first()
        if not batch or batch.course_id != course.id:
            raise HTTPException(400, "The selected batch does not belong to this course")

    # A timetable slot is optional context only. It never gates when a lecturer
    # may open attendance; the live session's own expiry controls availability.
    schedule = None
    if body.schedule_id or body.period:
        schedule = _own_schedule(db, user, course.id, body.period, body.schedule_id)
        if (body.schedule_id or body.period) and not schedule:
            raise HTTPException(404, "The selected timetable entry was not found for this course")

    now = app_now()
    period = (schedule.period if schedule else (body.period or f"ADHOC-{now.strftime('%H%M%S')}"))

    lat, lng, gps_accuracy = validated_gps(body.model_dump(), ceiling=GPS_SESSION_ACCURACY_CEILING)
    # The session radius bounds how far a student may be from the classroom; it
    # is not a bound on the device's reported accuracy. GPS accuracy is retained
    # as evidence, and validated_gps already rejects clearly unusable fixes.
    radius = body.radius_meters or _radius(db)

    # A second open request for the same course/batch/period today rotates the
    # token and closes the previous session so only one QR is ever live.
    existing = db.query(AttendanceSession).filter(
        AttendanceSession.faculty_id == user.id,
        AttendanceSession.course_id == course.id,
        AttendanceSession.date == now.date().isoformat(),
        AttendanceSession.period == period,
        AttendanceSession.is_open == True).first()
    if existing:
        existing.is_open = False
        existing.closed_at = now
        db.commit()

    minutes = body.session_minutes or _session_minutes(db)
    expires_at = now + timedelta(minutes=minutes)

    session = AttendanceSession(
        course_id=course.id, batch_id=batch.id if batch else (schedule.batch_id if schedule else None),
        faculty_id=user.id, schedule_id=schedule.id if schedule else None,
        academic_session_id=_current_session(db).id if _current_session(db) else None,
        date=now.date().isoformat(), period=period, topic=(body.topic or "").strip() or None,
        token=token_urlsafe(32), access_code=token_hex(4).upper(),
        latitude=lat, longitude=lng, radius_meters=radius,
        expires_at=expires_at, is_open=True, opened_at=now)
    db.add(session); db.commit(); db.refresh(session)
    audit(db, user, "open_attendance", "attendance_session", session.id,
          f"{course.code} {session.period}")
    publish_sync("attendance", {"action": "session_open", "course_id": course.id,
                                "session_id": session.id}, roles=["admin"])
    data = _session_dict(session, db)
    data["token"] = session.token
    data["qr_payload"] = {"session_id": session.id, "token": session.token}
    return data


@router.post("/faculty/attendance/sessions/{session_id}/close")
def close_session(session_id: int, user: User = Depends(require_roles("faculty", "admin")),
                  db: Session = Depends(get_db)):
    s = db.query(AttendanceSession).filter(AttendanceSession.id == session_id).first()
    if not s:
        raise HTTPException(404, "Attendance session not found")
    if user.role == "faculty" and s.faculty_id != user.id:
        raise HTTPException(403, "Not your attendance session")
    if not s.is_open:
        raise HTTPException(409, "This session is already closed")
    s.is_open = False
    s.closed_at = app_now()
    db.commit()
    audit(db, user, "close_attendance", "attendance_session", s.id, s.period)
    publish_sync("attendance", {"action": "session_close", "session_id": s.id}, roles=["admin"])
    return _session_dict(s, db, with_roster=True)


@router.get("/faculty/attendance/sessions")
def list_sessions(user: User = Depends(require_roles("faculty", "admin")),
                  db: Session = Depends(get_db), course_id: Optional[int] = None,
                  date_from: Optional[str] = None, date_to: Optional[str] = None):
    q = db.query(AttendanceSession)
    if user.role == "faculty":
        q = q.filter(AttendanceSession.faculty_id == user.id)
    if course_id:
        q = q.filter(AttendanceSession.course_id == course_id)
    if date_from:
        q = q.filter(AttendanceSession.date >= date_from)
    if date_to:
        q = q.filter(AttendanceSession.date <= date_to)
    rows = q.order_by(AttendanceSession.opened_at.desc()).limit(100).all()
    return [_session_dict(s, db) for s in rows]


@router.get("/faculty/attendance/sessions/{session_id}")
def get_session(session_id: int, user: User = Depends(require_roles("faculty", "admin")),
                db: Session = Depends(get_db)):
    s = db.query(AttendanceSession).filter(AttendanceSession.id == session_id).first()
    if not s:
        raise HTTPException(404, "Attendance session not found")
    if user.role == "faculty" and s.faculty_id != user.id:
        raise HTTPException(403, "Not your attendance session")
    return _session_dict(s, db, with_roster=True)


class AttendancePointsBody(BaseModel):
    points: Optional[float] = Field(default=None, ge=0, le=100)


@router.patch("/faculty/attendance/records/{attendance_id}/points")
def update_attendance_points(attendance_id: int, body: AttendancePointsBody,
                             user: User = Depends(require_roles("faculty", "admin")),
                             db: Session = Depends(get_db)):
    record = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not record:
        raise HTTPException(404, "Attendance record not found")
    if user.role == "faculty" and record.faculty_id != user.id:
        raise HTTPException(403, "You can only edit marks for your own courses")
    record.attendance_points = body.points
    db.commit()
    audit(db, user, "update_attendance_points", "attendance", record.id,
          "cleared" if body.points is None else f"{body.points:g} points")
    return {"message": "Attendance points saved", "attendance_id": record.id,
            "attendance_points": record.attendance_points}


# ── Student: mark attendance (QR + selfie + GPS) ─────────────────────────────
class MarkAttendanceBody(BaseModel):
    token: Optional[str] = Field(default=None, min_length=8)
    access_code: Optional[str] = Field(default=None, min_length=6, max_length=16)
    image: str = Field(min_length=32)
    latitude: float
    longitude: float
    accuracy: float = 30


@router.post("/student/attendance/mark")
def mark_attendance(body: MarkAttendanceBody, user: User = Depends(require_roles("student")),
                    db: Session = Depends(get_db)):
    if not user.is_approved:
        raise HTTPException(403, "Your student account is awaiting administrator approval")

    if not body.token and not body.access_code:
        raise HTTPException(422, "Scan the attendance QR or enter the attendance code")
    session_query = db.query(AttendanceSession).filter(AttendanceSession.is_open == True)
    if body.token:
        session_query = session_query.filter(AttendanceSession.token == body.token)
    else:
        session_query = session_query.filter(AttendanceSession.access_code == body.access_code.strip().upper())
    session = session_query.first()
    if not session:
        raise HTTPException(404, "This attendance QR is invalid or the session has closed.")

    now = app_now()
    if session.date != now.date().isoformat():
        raise HTTPException(400, "This attendance QR is for a different date.")
    if session.expires_at and session.expires_at < now:
        raise HTTPException(400, "This attendance QR has expired. Ask your lecturer to open a new session.")
    if session.latitude is None or session.longitude is None:
        raise HTTPException(409, "This session has no classroom location; ask the lecturer to reopen it.")

    lat, lng, gps_accuracy = validated_gps(body.model_dump())
    distance = haversine(session.latitude, session.longitude, lat, lng)
    radius = session.radius_meters or GPS_RADIUS_METERS
    # A very poor GPS fix makes the distance meaningless, so reject only clearly
    # unusable readings. Otherwise judge proximity by distance alone: the
    # reported accuracy is recorded as evidence but does not by itself exclude a
    # student who is physically inside the classroom radius.
    if gps_accuracy > GPS_ACCURACY_CEILING:
        raise HTTPException(400, "Your device could not obtain an accurate enough location fix "
                                 "to verify attendance. Move to an open area and try again.")
    if distance > radius:
        raise HTTPException(403, f"You are {int(distance)} m from the classroom. "
                                 f"You must be within {radius} m to mark attendance.")

    enrolment = db.query(CourseEnrolment).filter(
        CourseEnrolment.course_id == session.course_id,
        CourseEnrolment.student_id == user.id,
        CourseEnrolment.status == "approved").first()
    if not enrolment:
        raise HTTPException(403, "You must be registered for this course to mark its attendance.")
    if session.batch_id and enrolment.batch_id != session.batch_id:
        raise HTTPException(403, "This attendance session is for a different batch.")

    duplicate = db.query(Attendance).filter(
        Attendance.student_id == user.id,
        Attendance.attendance_session_id == session.id).first()
    if duplicate:
        raise HTTPException(409, "Your attendance has already been recorded for this class.")

    # Reject byte-for-byte reuse of an earlier attendance selfie. This is an
    # anti-replay safeguard, not facial recognition or liveness detection.
    image_hash = hashlib.sha256(body.image.encode("utf-8")).hexdigest()
    reused = db.query(Attendance).filter(
        Attendance.student_id == user.id, Attendance.image_sha256 == image_hash).first()
    if reused:
        raise HTTPException(409, "This exact selfie has already been used for attendance. Capture a new selfie.")
    image_ref = save_selfie(body.image)

    record = Attendance(
        student_id=user.id, faculty_id=session.faculty_id,
        attendance_session_id=session.id, course_id=session.course_id,
        batch_id=session.batch_id, academic_session_id=session.academic_session_id,
        date=session.date, period=session.period, status="present",
        method="QR_SELFIE_GPS" if body.token else "CODE_SELFIE_GPS", marked_by="student", image_ref=image_ref,
        image_sha256=image_hash, latitude=lat, longitude=lng, gps_accuracy=gps_accuracy,
        distance_meters=distance, marked_at=now)
    db.add(record); db.commit(); db.refresh(record)

    course = db.query(Course).filter(Course.id == session.course_id).first()
    audit(db, user, "mark_attendance", "attendance", record.id,
          f"{course.code if course else ''} {session.period} ({int(distance)} m)")
    publish_sync("attendance", {"action": "recorded", "session_id": session.id,
                                "course_id": session.course_id, "student_id": user.id},
                 user_ids=[session.faculty_id], roles=["admin"])
    notify(db, session.faculty_id, "Attendance marked",
           f"{user.name} ({user.index_number or '—'}) marked attendance for "
           f"{course.code if course else 'a class'} ({session.period}).",
           category="attendance", link="/faculty/attendance")
    return {"message": "Attendance marked successfully", "attendance_id": record.id,
            "student_name": user.name, "index_number": user.index_number,
            "course_code": course.code if course else None, "date": record.date,
            "period": record.period, "distance_meters": int(distance),
            "marked_at": record.marked_at.isoformat(),
            "method": "QR/session code + selfie + verified location"}


@router.get("/student/attendance/records")
def my_attendance(user: User = Depends(require_roles("student")), db: Session = Depends(get_db)):
    """The student's attendance, with a per-course percentage summary."""
    rows = db.query(Attendance).filter(Attendance.student_id == user.id).order_by(
        Attendance.marked_at.desc()).all()
    held = _held_sessions_for_student(db, user)
    # Per-course rate is based on sessions held for that course, matching the
    # overall figure so the dashboard and this page never disagree.
    summary = []
    for course_id, sessions in held.items():
        c = db.query(Course).filter(Course.id == course_id).first()
        present = sum(1 for s in sessions if any(
            a.attendance_session_id == s.id and a.status == "present" for a in rows))
        total = len(sessions)
        summary.append({"course_id": course_id,
                        "course_code": c.code if c else None,
                        "course_title": c.title if c else None,
                        "present": present, "total": total,
                        "rate": round((present / total) * 100, 1) if total else 0.0})
    summary.sort(key=lambda r: (r["course_code"] or ""))
    overall = student_attendance_summary(db, user)
    return {
        "records": [{
            "id": a.id, "course_id": a.course_id,
            "course_code": (db.query(Course).filter(Course.id == a.course_id).first().code
                            if a.course_id else None),
            "date": a.date, "period": a.period, "status": a.status,
            "method": a.method, "has_photo": bool(a.image_ref),
            "marked_at": a.marked_at.isoformat() if a.marked_at else None,
        } for a in rows],
        "summary": summary,
        "overall": {"present": overall["present_classes"], "total": overall["total_classes"],
                    "rate": overall["percentage"]},
    }


# ── Photo retrieval & corrections ────────────────────────────────────────────
@router.get("/attendance/photo/{attendance_id}")
def get_photo(attendance_id: int, user: User = Depends(require_roles("faculty", "admin")),
              db: Session = Depends(get_db)):
    a = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not a or not a.image_ref:
        raise HTTPException(404, "No attendance photo for this record")
    if user.role == "faculty":
        session = db.query(AttendanceSession).filter(
            AttendanceSession.id == a.attendance_session_id).first()
        owner = session.faculty_id if session else a.faculty_id
        if owner != user.id:
            raise HTTPException(403, "You can only view photos for your own classes")
    path = resolve_path(a.image_ref)
    media_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media_type, filename=f"attendance-{attendance_id}{path.suffix}")


class CorrectionBody(BaseModel):
    status: str
    reason: str = Field(min_length=3, max_length=300)


@router.post("/attendance/{attendance_id}/correction")
def correct_attendance(attendance_id: int, body: CorrectionBody,
                       user: User = Depends(require_roles("faculty", "admin")),
                       db: Session = Depends(get_db)):
    a = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not a:
        raise HTTPException(404, "Attendance record not found")
    if user.role == "faculty" and a.faculty_id != user.id:
        raise HTTPException(403, "You can only correct your own classes")
    if body.status not in ("present", "absent"):
        raise HTTPException(400, "Status must be 'present' or 'absent'")
    previous = a.status
    a.status = body.status
    db.add(AttendanceCorrection(attendance_id=a.id, previous_status=previous,
                                new_status=body.status, reason=body.reason.strip(),
                                actor_id=user.id, actor_name=user.name))
    db.commit()
    audit(db, user, "correct_attendance", "attendance", a.id,
          f"{previous} -> {body.status}: {body.reason.strip()}")
    notify(db, a.student_id, "Attendance corrected",
           f"Your attendance for {a.date} {a.period} was changed to {body.status}.",
           category="attendance", link="/student/attendance")
    publish_sync("attendance", {"action": "corrected", "attendance_id": a.id},
                 user_ids=[a.student_id], roles=["admin"])
    return {"message": "Attendance corrected", "attendance_id": a.id, "status": a.status}
