"""Institutional courses, timetable, enrolment and learning materials.

Everything here references the single canonical ``Course`` record. Timetable
entries store a ``course_id`` (plus a denormalised ``subject``/``subject_code``
mirror for legacy display), so creating a timetable entry never creates a new
course. Students see courses and timetable slots filtered by programme, level,
semester, enrolment and publication state.
"""
from datetime import datetime, timedelta
from secrets import token_urlsafe
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from deps import require_admin, require_roles
from models import (
    User, Course, CourseEnrolment, CoursePrerequisite, SystemSetting, Attendance,
    FacultySchedule, Venue, AcademicSession, Programme, LearningMaterial,
    CourseBatch, CourseProgramme, EnrolmentHistory, Department,
)
from realtime import audit, notify, notify_many, publish_sync
from seed import PERIOD_TIMES, ALL_PERIODS
from utils import natural_key

router = APIRouter()

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def _hhmm(value: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.strptime(value.strip(), "%H:%M")
    except (ValueError, AttributeError):
        return None


def _venue_name(db: Session, venue_id: Optional[int]) -> Optional[str]:
    if not venue_id:
        return None
    v = db.query(Venue).filter(Venue.id == venue_id).first()
    return v.name if v else None


# ═══════════════════════════════ Courses ════════════════════════════════════
class CourseCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    code: str = Field(min_length=2, max_length=30)
    lecturer_id: Optional[int] = None
    description: Optional[str] = None
    department: Optional[str] = None
    department_id: Optional[int] = None
    programme_id: Optional[int] = None
    programme_ids: list[int] = Field(default_factory=list)
    programme_name: Optional[str] = Field(default=None, max_length=180)
    institution_name: Optional[str] = Field(default=None, max_length=180)
    level: Optional[str] = None
    semester: Optional[str] = None
    academic_year: Optional[str] = None
    credit_hours: Optional[int] = Field(default=3, ge=0, le=30)
    registration_open: bool = True
    enrolment_requires_approval: bool = True
    is_published: bool = False
    prerequisite_ids: list[int] = Field(default_factory=list)
    batch_names: list[str] = Field(default_factory=list)


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    lecturer_id: Optional[int] = None
    description: Optional[str] = None
    department: Optional[str] = None
    department_id: Optional[int] = None
    programme_id: Optional[int] = None
    programme_ids: Optional[list[int]] = None
    level: Optional[str] = None
    semester: Optional[str] = None
    academic_year: Optional[str] = None
    credit_hours: Optional[int] = Field(default=None, ge=0, le=30)
    registration_open: Optional[bool] = None
    enrolment_requires_approval: Optional[bool] = None
    is_published: Optional[bool] = None
    prerequisite_ids: Optional[list[int]] = None


class JoinCourse(BaseModel):
    course_id: int
    batch_id: Optional[int] = None
    registration_code: Optional[str] = None


class JoinCourseByCode(BaseModel):
    registration_code: str = Field(min_length=6, max_length=80)
    batch_id: Optional[int] = None


class LecturerScheduleCreate(BaseModel):
    day_of_week: int = Field(ge=0, le=5)
    start_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    building: str = Field(min_length=1, max_length=120)
    room_no: str = Field(min_length=1, max_length=40)
    batch_id: Optional[int] = None
    class_type: str = "theory"


class Review(BaseModel):
    status: str


class WithdrawBody(BaseModel):
    reason: Optional[str] = None


class BatchChangeBody(BaseModel):
    batch_id: int


class SettingsBody(BaseModel):
    auto_approve_students: bool = False
    default_enrolment_approval: bool = True
    attendance_session_minutes: int = Field(default=10, ge=1, le=180)
    attendance_gps_radius_meters: int = Field(default=50, ge=10, le=500)
    max_credits_per_semester: int = Field(default=24, ge=1, le=60)


def serialize_course(c: Course, db: Session, lecturer=None, enrolment=None,
                     include_registration_code: bool = True, include_prereqs: bool = False):
    result = {
        "id": c.id, "title": c.title, "code": c.code, "description": c.description,
        "department": c.department, "department_id": c.department_id,
        "programme_id": c.programme_id, "programme_name": c.programme_name,
        "institution_name": c.institution_name, "level": c.level, "semester": c.semester,
        "academic_year": c.academic_year, "credit_hours": c.credit_hours,
        "lecturer_id": c.lecturer_id, "lecturer_name": lecturer.name if lecturer else None,
        "registration_open": c.registration_open,
        "enrolment_requires_approval": c.enrolment_requires_approval,
        "is_published": c.is_published,
        "enrolment_status": enrolment.status if enrolment else None,
    }
    if c.programme_id:
        p = db.query(Programme).filter(Programme.id == c.programme_id).first()
        result["programme_name"] = p.name if p else None
    if include_registration_code:
        result["registration_code"] = c.registration_code
        result["registration_code_expires_at"] = (
            c.registration_code_expires_at.isoformat() if c.registration_code_expires_at else None)
    if include_prereqs:
        rows = db.query(CoursePrerequisite).filter(CoursePrerequisite.course_id == c.id).all()
        prereqs = []
        for r in rows:
            p = db.query(Course).filter(Course.id == r.prerequisite_course_id).first()
            if p:
                prereqs.append({"id": p.id, "code": p.code, "title": p.title})
        result["prerequisites"] = prereqs
    return result


def _set_prerequisites(db: Session, course: Course, ids: list[int]):
    db.query(CoursePrerequisite).filter(CoursePrerequisite.course_id == course.id).delete()
    for pid in set(ids):
        if pid == course.id:
            raise HTTPException(400, "A course cannot be its own prerequisite")
        if not db.query(Course).filter(Course.id == pid).first():
            raise HTTPException(404, f"Prerequisite course {pid} not found")
        db.add(CoursePrerequisite(course_id=course.id, prerequisite_course_id=pid))


# ═══════════════════════════ Course batches ════════════════════════════════
def _batch_dict(b: CourseBatch, db: Session, with_counts: bool = False):
    lecturer = db.query(User).filter(User.id == b.lecturer_id).first() if b.lecturer_id else None
    data = {
        "id": b.id, "course_id": b.course_id, "name": b.name,
        "lecturer_id": b.lecturer_id, "lecturer_name": lecturer.name if lecturer else None,
        "capacity": b.capacity, "is_active": b.is_active,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }
    if with_counts:
        data["enrolled_count"] = db.query(CourseEnrolment).filter(
            CourseEnrolment.batch_id == b.id, CourseEnrolment.status == "approved").count()
    return data


def _course_batches(db: Session, course_id: int, active_only: bool = False):
    q = db.query(CourseBatch).filter(CourseBatch.course_id == course_id)
    if active_only:
        q = q.filter(CourseBatch.is_active == True)
    return q.order_by(CourseBatch.name).all()


def _course_programme_ids(db: Session, course: Course) -> set[int]:
    """Programmes a course is offered to: its primary programme plus any extras."""
    ids = {r.programme_id for r in db.query(CourseProgramme).filter(
        CourseProgramme.course_id == course.id).all()}
    if course.programme_id:
        ids.add(course.programme_id)
    return ids


def _course_open_to_programme(db: Session, course: Course, programme_id, programme_name=None) -> bool:
    """Match a user's free-text programme when no shared directory ID exists."""
    ids = _course_programme_ids(db, course)
    if not ids and not (course.programme_name or "").strip():
        return True
    if programme_id and programme_id in ids:
        return True
    accepted = {((course.programme_name or "").strip().casefold())} if course.programme_name else set()
    if ids:
        accepted.update((p.name or "").strip().casefold() for p in db.query(Programme).filter(Programme.id.in_(ids)).all())
    return bool(programme_name and programme_name.strip().casefold() in accepted)


def _set_course_programmes(db: Session, course: Course, programme_ids: list[int]):
    db.query(CourseProgramme).filter(CourseProgramme.course_id == course.id).delete()
    for pid in set(programme_ids):
        if not db.query(Programme).filter(Programme.id == pid).first():
            raise HTTPException(404, f"Programme {pid} not found")
        db.add(CourseProgramme(course_id=course.id, programme_id=pid))


@router.get("/academic/courses")
def list_courses(user: User = Depends(get_current_user), db: Session = Depends(get_db), q: str = ""):
    query = db.query(Course, User).join(User, Course.lecturer_id == User.id)
    if user.role == "faculty":
        query = query.filter(Course.lecturer_id == user.id)
    if q:
        query = query.filter(or_(Course.title.ilike(f"%{q}%"), Course.code.ilike(f"%{q}%")))
    rows = query.order_by(Course.title).all()
    if user.role == "student":
        enrolled = {e.course_id: e for e in db.query(CourseEnrolment).filter(
            CourseEnrolment.student_id == user.id).all()}
        visible = []
        for c, l in rows:
            in_enrolment = c.id in enrolled
            if not in_enrolment or enrolled[c.id].status == "withdrawn":
                continue
            visible.append(serialize_course(c, db, l, enrolled.get(c.id), include_registration_code=False))
        # Attach batch options so students can choose a batch when registering.
        for data in visible:
            data["batches"] = [_batch_dict(b, db, with_counts=True) for b in _course_batches(db, data["id"])]
        return visible
    out = []
    for c, l in rows:
        data = serialize_course(c, db, l, include_prereqs=(user.role == "admin"))
        if user.role == "admin":
            data["programme_ids"] = sorted(_course_programme_ids(db, c))
            data["batches"] = [_batch_dict(b, db, with_counts=True) for b in _course_batches(db, c.id)]
        out.append(data)
    return out


@router.get("/academic/courses/{course_id}")
def get_course(course_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.query(Course).filter(Course.id == course_id).first()
    if not c:
        raise HTTPException(404, "Course not found")
    if user.role == "faculty" and c.lecturer_id != user.id:
        raise HTTPException(403, "Not your course")
    lecturer = db.query(User).filter(User.id == c.lecturer_id).first()
    enrolment = db.query(CourseEnrolment).filter_by(course_id=c.id, student_id=user.id).first() \
        if user.role == "student" else None
    include_code = user.role in ("admin", "faculty")
    return serialize_course(c, db, lecturer, enrolment,
                            include_registration_code=include_code,
                            include_prereqs=(user.role != "student"))


@router.post("/academic/courses", status_code=201)
def create_course(body: CourseCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "faculty":
        raise HTTPException(403, "Only lecturers can create teaching courses. Administrators have monitoring and directory-management access.")
    lecturer_id = user.id
    lecturer = db.query(User).filter(User.id == lecturer_id, User.role == "faculty").first()
    if not lecturer:
        raise HTTPException(404, "Lecturer not found")
    code = body.code.strip().upper()
    if db.query(Course).filter(Course.code == code, Course.institution_name == lecturer.institution_name).first():
        raise HTTPException(409, "Course code already exists in your institution")
    requested_programme_id = body.programme_id or (body.programme_ids[0] if body.programme_ids else None)
    if not requested_programme_id:
        raise HTTPException(422, "Select an eligible programme from the academic directory")
    programme = db.query(Programme).filter(Programme.id == requested_programme_id).first()
    if not programme:
        raise HTTPException(404, "Programme not found")
    if (programme.institution_name or "").strip().casefold() != (lecturer.institution_name or "").strip().casefold():
        raise HTTPException(403, "You can only create courses for programmes in your institution")
    data = body.model_dump(exclude={"code", "prerequisite_ids", "programme_ids", "batch_names"})
    data["lecturer_id"] = lecturer.id
    data["programme_id"] = programme.id
    data["institution_name"] = (body.institution_name or lecturer.institution_name or "").strip() or None
    if not data.get("programme_name") and programme:
        data["programme_name"] = programme.name
    if programme:
        department = db.query(Department).filter(Department.id == programme.department_id).first() if programme.department_id else None
        data["department_id"] = programme.department_id
        data["department"] = department.name if department else None
    elif user.role == "faculty":
        data["department_id"] = user.department_id
        data["department"] = body.department or user.department
    c = Course(**data, code=code, registration_code=token_urlsafe(9),
               registration_code_expires_at=datetime.utcnow() + timedelta(days=7))
    db.add(c); db.flush()
    programme_ids = list(set(body.programme_ids + [requested_programme_id]))
    linked_programmes = db.query(Programme).filter(Programme.id.in_(programme_ids)).all()
    if len(linked_programmes) != len(programme_ids):
        db.rollback()
        raise HTTPException(422, "One or more selected programmes do not exist")
    if any((p.institution_name or "").strip().casefold() != (lecturer.institution_name or "").strip().casefold() for p in linked_programmes):
        db.rollback()
        raise HTTPException(403, "A course cannot be linked to programmes from another institution")
    _set_course_programmes(db, c, programme_ids)
    for name in body.batch_names:
        clean = (name or "").strip()
        if clean and not db.query(CourseBatch).filter_by(course_id=c.id, name=clean).first():
            db.add(CourseBatch(course_id=c.id, name=clean, lecturer_id=lecturer.id))
    if body.prerequisite_ids:
        _set_prerequisites(db, c, body.prerequisite_ids)
    db.commit(); db.refresh(c)
    audit(db, user, "create", "course", c.id, f"{c.code} {c.title}")
    publish_sync("courses", {"action": "create", "id": c.id, "code": c.code},
                 roles=["admin", "faculty"])
    if programme_ids and c.is_published:
        student_ids = [u.id for u in db.query(User).filter(
            User.role == "student", User.programme_id.in_(programme_ids),
            User.is_approved == True).all()]
        notify_many(db, student_ids, "New course available",
                    f"{c.code} — {c.title} is now open for registration.",
                    category="course", link="/student/courses")
    result = serialize_course(c, db, lecturer, include_prereqs=True)
    result["programme_ids"] = sorted(_course_programme_ids(db, c))
    result["batches"] = [_batch_dict(b, db) for b in _course_batches(db, c.id)]
    return result


@router.post("/faculty/courses/{course_id}/schedule", status_code=201)
def create_lecturer_schedule(course_id: int, body: LecturerScheduleCreate,
                             user: User = Depends(require_roles("faculty")),
                             db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id, Course.lecturer_id == user.id).first()
    if not course:
        raise HTTPException(404, "Course not found in your lecturer account")
    start = _hhmm(body.start_time); end = _hhmm(body.end_time)
    if not start or not end or start >= end:
        raise HTTPException(422, "Class end time must be later than its start time")
    if body.batch_id:
        batch = db.query(CourseBatch).filter(CourseBatch.id == body.batch_id,
                                             CourseBatch.course_id == course.id,
                                             CourseBatch.is_active == True).first()
        if not batch:
            raise HTTPException(404, "Selected course batch was not found")
    overlaps = db.query(FacultySchedule).filter(
        FacultySchedule.faculty_id == user.id,
        FacultySchedule.day_of_week == body.day_of_week).all()
    for slot in overlaps:
        slot_start = _hhmm(slot.start_time); slot_end = _hhmm(slot.end_time)
        if slot_start and slot_end and start < slot_end and end > slot_start:
            raise HTTPException(409, f"This time overlaps with {slot.subject} ({slot.start_time}–{slot.end_time})")
    # A room is a shared institutional resource: prevent two lecturers
    # from booking the same building/room during overlapping times.
    room_key = (body.building.strip().casefold(), body.room_no.strip().casefold())
    room_slots = db.query(FacultySchedule, Venue).join(
        Venue, FacultySchedule.venue_id == Venue.id
    ).filter(FacultySchedule.day_of_week == body.day_of_week).all()
    for existing, existing_venue in room_slots:
        existing_key = (
            (existing_venue.building or "").strip().casefold(),
            (existing.room_no or "").strip().casefold(),
        )
        old_start = _hhmm(existing.start_time)
        old_end = _hhmm(existing.end_time)
        if existing_key == room_key and old_start and old_end and start < old_end and end > old_start:
            owner = db.query(User).filter(User.id == existing.faculty_id).first()
            owner_name = owner.name if owner else "another lecturer"
            raise HTTPException(
                409,
                f"This room is already booked by {owner_name} "
                f"({existing.start_time}–{existing.end_time})",
            )

    venue_name = f"{body.building.strip()} — Room {body.room_no.strip()}"
    venue = db.query(Venue).filter(Venue.name == venue_name).first()
    if not venue:
        venue = Venue(name=venue_name, building=body.building.strip(), venue_type="lecture", is_active=True)
        db.add(venue); db.flush()
    period = f"D{body.day_of_week}-{body.start_time.replace(':', '')}"
    row = FacultySchedule(
        faculty_id=user.id, day_of_week=body.day_of_week, period=period,
        subject=course.title, subject_code=course.code, class_type=body.class_type,
        room_no=body.room_no.strip(), start_time=body.start_time, end_time=body.end_time,
        course_id=course.id, venue_id=venue.id, batch_id=body.batch_id,
        academic_session_id=_current_session(db).id if _current_session(db) else None,
        is_published=True)
    db.add(row); db.commit(); db.refresh(row)
    audit(db, user, "create", "course_schedule", row.id, f"{course.code} {DAY_NAMES[body.day_of_week]} {body.start_time}-{body.end_time}")
    publish_sync("timetable", {"action": "create", "id": row.id, "course_id": course.id}, roles=["admin", "faculty", "student"])
    return _slot_dict(row, db)


@router.put("/faculty/schedules/{schedule_id}")
def update_lecturer_schedule(schedule_id: int, body: LecturerScheduleCreate,
                             user: User = Depends(require_roles("faculty")),
                             db: Session = Depends(get_db)):
    row = db.query(FacultySchedule).filter(FacultySchedule.id == schedule_id,
                                           FacultySchedule.faculty_id == user.id).first()
    if not row:
        raise HTTPException(404, "Class schedule not found in your lecturer account")
    course = db.query(Course).filter(Course.id == row.course_id, Course.lecturer_id == user.id).first()
    if not course:
        raise HTTPException(404, "Course not found in your lecturer account")
    start = _hhmm(body.start_time); end = _hhmm(body.end_time)
    if not start or not end or start >= end:
        raise HTTPException(422, "Class end time must be later than its start time")
    if body.batch_id:
        batch = db.query(CourseBatch).filter(CourseBatch.id == body.batch_id,
                                             CourseBatch.course_id == course.id,
                                             CourseBatch.is_active == True).first()
        if not batch:
            raise HTTPException(404, "Selected course batch was not found")
    overlaps = db.query(FacultySchedule).filter(
        FacultySchedule.faculty_id == user.id,
        FacultySchedule.day_of_week == body.day_of_week,
        FacultySchedule.id != schedule_id).all()
    for slot in overlaps:
        slot_start = _hhmm(slot.start_time); slot_end = _hhmm(slot.end_time)
        if slot_start and slot_end and start < slot_end and end > slot_start:
            raise HTTPException(409, f"This time overlaps with {slot.subject} ({slot.start_time}–{slot.end_time})")
    # Exclude the schedule being edited, but reject overlaps with every
    # other lecturer's booking for the same physical room.
    room_key = (body.building.strip().casefold(), body.room_no.strip().casefold())
    room_slots = db.query(FacultySchedule, Venue).join(
        Venue, FacultySchedule.venue_id == Venue.id
    ).filter(
        FacultySchedule.day_of_week == body.day_of_week,
        FacultySchedule.id != schedule_id,
    ).all()
    for existing, existing_venue in room_slots:
        existing_key = (
            (existing_venue.building or "").strip().casefold(),
            (existing.room_no or "").strip().casefold(),
        )
        old_start = _hhmm(existing.start_time)
        old_end = _hhmm(existing.end_time)
        if existing_key == room_key and old_start and old_end and start < old_end and end > old_start:
            owner = db.query(User).filter(User.id == existing.faculty_id).first()
            owner_name = owner.name if owner else "another lecturer"
            raise HTTPException(
                409,
                f"This room is already booked by {owner_name} "
                f"({existing.start_time}–{existing.end_time})",
            )

    venue_name = f"{body.building.strip()} — Room {body.room_no.strip()}"
    venue = db.query(Venue).filter(Venue.name == venue_name).first()
    if not venue:
        venue = Venue(name=venue_name, building=body.building.strip(), venue_type="lecture", is_active=True)
        db.add(venue); db.flush()
    row.day_of_week = body.day_of_week
    row.period = f"D{body.day_of_week}-{body.start_time.replace(':', '')}"
    row.start_time = body.start_time
    row.end_time = body.end_time
    row.room_no = body.room_no.strip()
    row.class_type = body.class_type
    row.venue_id = venue.id
    row.batch_id = body.batch_id
    db.commit(); db.refresh(row)
    audit(db, user, "update", "course_schedule", row.id,
          f"{course.code} {DAY_NAMES[body.day_of_week]} {body.start_time}-{body.end_time}")
    publish_sync("timetable", {"action": "update", "id": row.id, "course_id": course.id},
                 roles=["admin", "faculty", "student"])
    return _slot_dict(row, db)


@router.delete("/faculty/schedules/{schedule_id}")
def delete_lecturer_schedule(schedule_id: int, user: User = Depends(require_roles("faculty")),
                             db: Session = Depends(get_db)):
    row = db.query(FacultySchedule).filter(FacultySchedule.id == schedule_id,
                                           FacultySchedule.faculty_id == user.id).first()
    if not row:
        raise HTTPException(404, "Class schedule not found in your lecturer account")
    db.delete(row); db.commit()
    audit(db, user, "delete", "course_schedule", schedule_id)
    publish_sync("timetable", {"action": "delete", "id": schedule_id}, roles=["admin", "faculty", "student"])
    return {"message": "Class schedule removed"}


@router.patch("/academic/courses/{course_id}")
def update_course(course_id: int, body: CourseUpdate, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    c = db.query(Course).filter(Course.id == course_id).first()
    if not c:
        raise HTTPException(404, "Course not found")
    if user.role not in ("admin", "faculty") or (user.role == "faculty" and c.lecturer_id != user.id):
        raise HTTPException(403, "Not your course")
    updates = body.model_dump(exclude_unset=True)
    prereqs = updates.pop("prerequisite_ids", None)
    programme_ids = updates.pop("programme_ids", None)
    if "lecturer_id" in updates and user.role == "admin":
        if not db.query(User).filter(User.id == updates["lecturer_id"], User.role == "faculty").first():
            raise HTTPException(404, "Lecturer not found")
    if user.role == "faculty":
        allowed = {"registration_open", "enrolment_requires_approval", "is_published", "description",
                   "title", "level", "semester", "academic_year", "credit_hours", "programme_id"}
        updates = {k: v for k, v in updates.items() if k in allowed}
        programme_ids = None
        if "programme_id" in updates:
            selected = db.query(Programme).filter(Programme.id == updates["programme_id"]).first()
            if not selected:
                raise HTTPException(404, "Programme not found")
            if (selected.institution_name or "").strip().casefold() != (user.institution_name or "").strip().casefold():
                raise HTTPException(403, "You can only assign courses to programmes in your institution")
            c.programme_id = selected.id
            c.programme_name = selected.name
            c.department_id = selected.department_id
            department = db.query(Department).filter(Department.id == selected.department_id).first() if selected.department_id else None
            c.department = department.name if department else None
            _set_course_programmes(db, c, [selected.id])
            updates.pop("programme_id", None)
    for k, v in updates.items():
        setattr(c, k, v)
    if programme_ids is not None and user.role == "admin":
        ids = list(programme_ids)
        if c.programme_id and c.programme_id not in ids:
            ids.append(c.programme_id)
        _set_course_programmes(db, c, ids)
    if prereqs is not None and user.role == "admin":
        _set_prerequisites(db, c, prereqs)
    db.commit(); db.refresh(c)
    lecturer = db.query(User).filter(User.id == c.lecturer_id).first()
    audit(db, user, "update", "course", c.id, f"{c.code} {c.title}")
    publish_sync("courses", {"action": "update", "id": c.id, "code": c.code},
                 roles=["admin", "faculty"])
    return serialize_course(c, db, lecturer, include_prereqs=True)


@router.delete("/academic/courses/{course_id}")
def delete_course(course_id: int, user: User = Depends(require_roles("admin", "faculty")),
                  db: Session = Depends(get_db)):
    c = db.query(Course).filter(Course.id == course_id).first()
    if not c:
        raise HTTPException(404, "Course not found")
    if user.role == "faculty" and c.lecturer_id != user.id:
        raise HTTPException(403, "You can only delete your own courses")
    if db.query(CourseEnrolment).filter(CourseEnrolment.course_id == course_id).count() or \
       db.query(Attendance).filter(Attendance.course_id == course_id).count():
        raise HTTPException(409, "This course has enrolment or attendance history. "
                                 "Close registration instead of deleting it.")
    if db.query(FacultySchedule).filter(FacultySchedule.course_id == course_id).count():
        raise HTTPException(409, "This course is used by timetable entries. Remove those entries first.")
    db.query(CoursePrerequisite).filter(
        or_(CoursePrerequisite.course_id == course_id,
            CoursePrerequisite.prerequisite_course_id == course_id)).delete()
    db.delete(c); db.commit()
    audit(db, user, "delete", "course", course_id, f"{c.code} {c.title}")
    publish_sync("courses", {"action": "delete", "id": course_id}, roles=["admin", "faculty"])
    return {"message": "Course deleted"}


class RotateCodeBody(BaseModel):
    expires_in_hours: int = Field(default=168, ge=1, le=8760)


@router.post("/academic/courses/{course_id}/registration-code")
def rotate_registration_code(course_id: int, body: RotateCodeBody,
                             user: User = Depends(require_roles("admin", "faculty")),
                             db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(404, "Course not found")
    if user.role == "faculty" and course.lecturer_id != user.id:
        raise HTTPException(403, "You can only change codes for your own courses")
    course.registration_code = token_urlsafe(9)
    course.registration_code_expires_at = datetime.utcnow() + timedelta(hours=body.expires_in_hours)
    db.commit(); db.refresh(course)
    audit(db, user, "rotate_code", "course", course.id, course.code)
    return {"course_id": course.id, "registration_code": course.registration_code,
            "expires_at": course.registration_code_expires_at.isoformat(),
            "message": "A new registration code has been generated. The previous code is now invalid."}


# ═════════════════════════ Course batch management ══════════════════════════
class BatchBody(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    lecturer_id: Optional[int] = None
    capacity: Optional[int] = Field(default=None, ge=1)   # omit / null = unlimited
    is_active: bool = True


class BatchUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    lecturer_id: Optional[int] = None
    capacity: Optional[int] = Field(default=None, ge=1)
    is_active: Optional[bool] = None


@router.get("/admin/courses/{course_id}/batches")
def list_batches(course_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not db.query(Course).filter(Course.id == course_id).first():
        raise HTTPException(404, "Course not found")
    return [_batch_dict(b, db, with_counts=True) for b in _course_batches(db, course_id)]


@router.post("/admin/courses/{course_id}/batches", status_code=201)
def create_batch(course_id: int, body: BatchBody, user: User = Depends(require_admin),
                 db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(404, "Course not found")
    name = body.name.strip()
    if db.query(CourseBatch).filter_by(course_id=course_id, name=name).first():
        raise HTTPException(409, "This course already has a batch with that name")
    if body.lecturer_id and not db.query(User).filter(User.id == body.lecturer_id, User.role == "faculty").first():
        raise HTTPException(404, "Lecturer not found")
    b = CourseBatch(course_id=course_id, name=name, lecturer_id=body.lecturer_id,
                    capacity=body.capacity, is_active=body.is_active)
    db.add(b); db.commit(); db.refresh(b)
    audit(db, user, "create", "course_batch", b.id, f"{course.code} / {b.name}")
    publish_sync("batches", {"action": "create", "course_id": course_id, "batch_id": b.id},
                 roles=["admin", "faculty"])
    return _batch_dict(b, db, with_counts=True)


@router.put("/admin/batches/{batch_id}")
def update_batch(batch_id: int, body: BatchUpdate, user: User = Depends(require_admin),
                 db: Session = Depends(get_db)):
    b = db.query(CourseBatch).filter(CourseBatch.id == batch_id).first()
    if not b:
        raise HTTPException(404, "Batch not found")
    if body.name is not None:
        name = body.name.strip()
        dup = db.query(CourseBatch).filter(CourseBatch.course_id == b.course_id,
                                           CourseBatch.name == name, CourseBatch.id != b.id).first()
        if dup:
            raise HTTPException(409, "Another batch of this course already uses that name")
        b.name = name
    if body.lecturer_id is not None:
        if body.lecturer_id and not db.query(User).filter(
                User.id == body.lecturer_id, User.role == "faculty").first():
            raise HTTPException(404, "Lecturer not found")
        b.lecturer_id = body.lecturer_id or None
    if body.capacity is not None:
        b.capacity = body.capacity
    if body.is_active is not None:
        b.is_active = body.is_active
    db.commit(); db.refresh(b)
    audit(db, user, "update", "course_batch", b.id, b.name)
    publish_sync("batches", {"action": "update", "course_id": b.course_id, "batch_id": b.id},
                 roles=["admin", "faculty"])
    return _batch_dict(b, db, with_counts=True)


@router.delete("/admin/batches/{batch_id}")
def delete_batch(batch_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    b = db.query(CourseBatch).filter(CourseBatch.id == batch_id).first()
    if not b:
        raise HTTPException(404, "Batch not found")
    if db.query(CourseEnrolment).filter(CourseEnrolment.batch_id == batch_id).count():
        raise HTTPException(409, "Students are enrolled in this batch. Deactivate it instead of deleting.")
    if db.query(FacultySchedule).filter(FacultySchedule.batch_id == batch_id).count():
        raise HTTPException(409, "Timetable entries use this batch. Remove them first.")
    db.delete(b); db.commit()
    audit(db, user, "delete", "course_batch", batch_id, b.name)
    publish_sync("batches", {"action": "delete", "batch_id": batch_id}, roles=["admin", "faculty"])
    return {"message": "Batch deleted"}


# ═══════════════════════════════ Enrolment ══════════════════════════════════
def _current_session(db: Session) -> Optional[AcademicSession]:
    return db.query(AcademicSession).filter(AcademicSession.is_current == True).first()


def _enrolled_credits(db: Session, student_id: int) -> int:
    rows = db.query(CourseEnrolment, Course).join(
        Course, CourseEnrolment.course_id == Course.id).filter(
        CourseEnrolment.student_id == student_id,
        CourseEnrolment.status.in_(("pending", "approved"))).all()
    return sum((c.credit_hours or 0) for _, c in rows)


def _enrolment_dict(e: CourseEnrolment, c: Course, s: User, db: Session):
    batch = db.query(CourseBatch).filter(CourseBatch.id == e.batch_id).first() if e.batch_id else None
    lecturer = db.query(User).filter(User.id == c.lecturer_id).first()
    return {
        "id": e.id, "course_id": c.id, "course": c.title, "course_code": c.code,
        "credit_hours": c.credit_hours, "level": c.level, "semester": c.semester,
        "batch_id": e.batch_id, "batch_name": batch.name if batch else None,
        "lecturer_name": lecturer.name if lecturer else None,
        "student_id": s.id, "student_name": s.name, "index_number": s.index_number,
        "email": s.email, "department": s.department, "status": e.status,
        "requested_at": e.requested_at.isoformat() if e.requested_at else None,
        "reviewed_at": e.reviewed_at.isoformat() if e.reviewed_at else None,
    }


@router.get("/academic/course-preview")
def preview_course_by_code(code: str, user: User = Depends(require_roles("student")),
                           db: Session = Depends(get_db)):
    if not user.is_approved:
        raise HTTPException(403, "Your student account is awaiting administrator approval")
    course = db.query(Course).filter(Course.registration_code == code.strip()).first()
    if not course:
        raise HTTPException(404, "Course registration code is invalid")
    if course.registration_code_expires_at and course.registration_code_expires_at < datetime.utcnow():
        raise HTTPException(410, "This course registration code has expired. Ask the lecturer for a new code.")
    if not course.registration_open or not course.is_published:
        raise HTTPException(403, "This course is not currently open for registration")
    if course.institution_name and user.institution_name and course.institution_name.strip().casefold() != user.institution_name.strip().casefold():
        raise HTTPException(403, "This course belongs to a different institution")
    if not _course_open_to_programme(db, course, user.programme_id, user.programme_name):
        raise HTTPException(403, "This course is not offered to your programme")
    if course.level and user.level and str(user.level) not in str(course.level):
        raise HTTPException(403, f"This course is offered at level {course.level}")
    lecturer = db.query(User).filter(User.id == course.lecturer_id).first()
    existing = db.query(CourseEnrolment).filter_by(course_id=course.id, student_id=user.id).first()
    if existing and existing.status != "withdrawn":
        raise HTTPException(409, f"You already have a {existing.status} enrolment for this course")
    data = serialize_course(course, db, lecturer, include_registration_code=False)
    data["lecturer_name"] = lecturer.name if lecturer else None
    data["enrolment_requires_approval"] = course.enrolment_requires_approval
    data["batches"] = [_batch_dict(b, db, with_counts=True) for b in _course_batches(db, course.id, active_only=True)]
    return data


@router.post("/academic/enrol-by-code")
def enrol_by_registration_code(body: JoinCourseByCode,
                               user: User = Depends(require_roles("student")),
                               db: Session = Depends(get_db)):
    if not user.is_approved:
        raise HTTPException(403, "Your student account is awaiting approval")
    code = body.registration_code.strip()
    course = db.query(Course).filter(Course.registration_code == code).first()
    if not course:
        raise HTTPException(404, "Course registration code is invalid")
    if course.registration_code_expires_at and course.registration_code_expires_at < datetime.utcnow():
        raise HTTPException(410, "This course registration code has expired. Ask the lecturer for a new code.")
    if not course.registration_open or not course.is_published:
        raise HTTPException(403, "This course is not currently open for registration")
    return enrol(JoinCourse(course_id=course.id, batch_id=body.batch_id, registration_code=code), user, db)


@router.post("/academic/enrol")
def enrol(body: JoinCourse, user: User = Depends(require_roles("student")), db: Session = Depends(get_db)):
    """Register a student for a course and one of its batches.

    Eligibility, prerequisites, registration windows and credit limits are
    validated. Courses configured to require lecturer approval remain pending;
    other courses activate immediately. Batch capacity is enforced when set.
    """
    if not user.is_approved:
        raise HTTPException(403, "Your student account is awaiting approval")

    c = db.query(Course).filter(Course.id == body.course_id).first()
    if not c:
        raise HTTPException(404, "Course not found")
    if not c.registration_open or not c.is_published:
        raise HTTPException(403, "This course is not currently open for registration")
    if not body.registration_code or body.registration_code != c.registration_code:
        raise HTTPException(403, "A valid lecturer-issued course registration code is required")
    if c.registration_code_expires_at and c.registration_code_expires_at < datetime.utcnow():
        raise HTTPException(410, "This course registration code has expired. Ask the lecturer for a new code.")
    if c.institution_name and user.institution_name and c.institution_name.strip().casefold() != user.institution_name.strip().casefold():
        raise HTTPException(403, "This course belongs to a different institution")
    if not _course_open_to_programme(db, c, user.programme_id, user.programme_name):
        raise HTTPException(403, "This course is not offered to your programme")
    if c.level and user.level and str(user.level) not in str(c.level):
        raise HTTPException(403, f"This course is offered at level {c.level}")

    existing = db.query(CourseEnrolment).filter_by(course_id=c.id, student_id=user.id).first()
    if existing and existing.status != "withdrawn":
        raise HTTPException(409, "You have already registered for this course")

    if c.institution_name and user.institution_name and c.institution_name.strip().casefold() != user.institution_name.strip().casefold():
        raise HTTPException(403, "This course belongs to a different institution")
    if not _course_open_to_programme(db, c, user.programme_id, user.programme_name):
        raise HTTPException(403, "This course is not offered to your programme")
    if c.level and user.level and str(user.level) not in str(c.level):
        raise HTTPException(403, f"This course is offered at level {c.level}")

    session = _current_session(db)
    if session and not session.registration_open:
        raise HTTPException(403, "Course registration is currently closed for the active semester")

    # Batch is required when the course defines any active batch.
    batches = _course_batches(db, c.id, active_only=True)
    batch = None
    if body.batch_id is not None:
        batch = db.query(CourseBatch).filter(CourseBatch.id == body.batch_id).first()
        if not batch or batch.course_id != c.id:
            raise HTTPException(400, "The selected batch does not belong to this course")
        if not batch.is_active:
            raise HTTPException(400, "The selected batch is not active")
    elif batches:
        raise HTTPException(400, "Select a batch for this course")

    # Optional capacity is honoured only when an administrator set a positive
    # limit; the default (NULL) is unlimited.
    if batch and batch.capacity and batch.capacity > 0:
        taken = db.query(CourseEnrolment).filter(
            CourseEnrolment.batch_id == batch.id,
            CourseEnrolment.status.in_(("pending", "approved"))).count()
        if taken >= batch.capacity:
            raise HTTPException(409, f"Batch {batch.name} is full")

    prereqs = db.query(CoursePrerequisite).filter(CoursePrerequisite.course_id == c.id).all()
    if prereqs:
        approved = {e.course_id for e in db.query(CourseEnrolment).filter(
            CourseEnrolment.student_id == user.id, CourseEnrolment.status == "approved").all()}
        missing = [p.prerequisite_course_id for p in prereqs if p.prerequisite_course_id not in approved]
        if missing:
            codes = [x.code for x in db.query(Course).filter(Course.id.in_(missing)).all()]
            raise HTTPException(403, f"You must complete these prerequisites first: {', '.join(codes)}")

    cap_setting = db.query(SystemSetting).filter_by(key="max_credits_per_semester").first()
    cap = int(cap_setting.value) if cap_setting else 24
    already = 0 if (existing and existing.status == "withdrawn") else _enrolled_credits(db, user.id)
    if already + (c.credit_hours or 0) > cap:
        raise HTTPException(403, f"Adding this course exceeds the {cap}-credit semester limit")

    enrolment_status = "pending" if c.enrolment_requires_approval else "approved"
    if existing:   # re-registering after withdrawal
        existing.status = enrolment_status
        existing.batch_id = batch.id if batch else None
        existing.requested_at = datetime.utcnow()
        existing.withdrawn_at = None
        existing.withdrawal_reason = None
        e = existing
    else:
        e = CourseEnrolment(course_id=c.id, student_id=user.id, status=enrolment_status,
                            batch_id=batch.id if batch else None)
        db.add(e)
    db.flush()
    db.add(EnrolmentHistory(enrolment_id=e.id, student_id=user.id, course_id=c.id,
                            batch_id=e.batch_id, action="registered", actor_id=user.id,
                            detail=f"Batch {batch.name}" if batch else None))
    db.commit(); db.refresh(e)
    audit(db, user, "enrol", "course", c.id,
          f"{c.code}{' / ' + batch.name if batch else ''}")
    notify(db, c.lecturer_id, "New enrolment",
           f"{user.name} ({user.index_number or '—'}) registered for {c.code} — {c.title}"
           f"{' (Batch ' + batch.name + ')' if batch else ''}.",
           category="enrolment", link="/faculty/academic")
    publish_sync("enrolments", {"action": "create", "course_id": c.id, "student_id": user.id},
                 roles=["admin"], user_ids=[c.lecturer_id])
    return {"message": "Your course enrolment request has been submitted" if enrolment_status == "pending" else "You are now registered for this course", "status": enrolment_status,
            "course_id": c.id, "batch_id": e.batch_id, "batch_name": batch.name if batch else None}


@router.delete("/academic/enrol/{enrolment_id}")
def withdraw(enrolment_id: int, body: WithdrawBody = Body(default=WithdrawBody()),
             user: User = Depends(require_roles("student")), db: Session = Depends(get_db)):
    """Withdraw from a course within the permitted (open-registration) window."""
    e = db.query(CourseEnrolment).filter(CourseEnrolment.id == enrolment_id,
                                         CourseEnrolment.student_id == user.id).first()
    if not e:
        raise HTTPException(404, "Enrolment not found")
    c = db.query(Course).filter(Course.id == e.course_id).first()
    session = _current_session(db)
    if session and not session.registration_open:
        raise HTTPException(403, "Course withdrawal is closed for the active semester")
    if e.status == "withdrawn":
        raise HTTPException(409, "You have already withdrawn from this course")
    e.status = "withdrawn"
    e.withdrawn_at = datetime.utcnow()
    e.withdrawal_reason = (body.reason or "").strip() or None
    db.add(EnrolmentHistory(enrolment_id=e.id, student_id=user.id, course_id=e.course_id,
                            batch_id=e.batch_id, action="withdrawn", actor_id=user.id,
                            detail=e.withdrawal_reason))
    db.commit()
    audit(db, user, "withdraw", "course", e.course_id, c.code if c else "")
    notify(db, c.lecturer_id if c else user.id, "Course withdrawal",
           f"{user.name} ({user.index_number or '—'}) withdrew from {c.code if c else 'a course'}.",
           category="enrolment", link="/faculty/academic")
    publish_sync("enrolments", {"action": "withdraw", "course_id": e.course_id, "student_id": user.id},
                 roles=["admin"])
    return {"message": "You have withdrawn from this course"}


@router.patch("/academic/enrol/{enrolment_id}/batch")
def change_batch(enrolment_id: int, body: BatchChangeBody,
                 user: User = Depends(require_roles("student")), db: Session = Depends(get_db)):
    """Change the batch for an existing enrolment, within the open window."""
    e = db.query(CourseEnrolment).filter(CourseEnrolment.id == enrolment_id,
                                         CourseEnrolment.student_id == user.id).first()
    if not e:
        raise HTTPException(404, "Enrolment not found")
    if e.status != "approved":
        raise HTTPException(400, "Only an approved enrolment can change batch")
    session = _current_session(db)
    if session and not session.registration_open:
        raise HTTPException(403, "Batch changes are closed for the active semester")
    batch = db.query(CourseBatch).filter(CourseBatch.id == body.batch_id).first()
    if not batch or batch.course_id != e.course_id or not batch.is_active:
        raise HTTPException(400, "The selected batch does not belong to this course")
    if batch.capacity and batch.capacity > 0:
        taken = db.query(CourseEnrolment).filter(
            CourseEnrolment.batch_id == batch.id, CourseEnrolment.status == "approved").count()
        if taken >= batch.capacity and e.batch_id != batch.id:
            raise HTTPException(409, f"Batch {batch.name} is full")
    previous = e.batch_id
    e.batch_id = batch.id
    db.add(EnrolmentHistory(enrolment_id=e.id, student_id=user.id, course_id=e.course_id,
                            batch_id=batch.id, action="batch_changed", actor_id=user.id,
                            detail=f"{previous} -> {batch.id}"))
    db.commit()
    audit(db, user, "change_batch", "course_enrolment", e.id, f"batch {batch.name}")
    return {"message": f"Batch changed to {batch.name}", "batch_id": batch.id, "batch_name": batch.name}


@router.get("/academic/enrolments")
def enrolments(user: User = Depends(get_current_user), db: Session = Depends(get_db),
               status: Optional[str] = None, course_id: Optional[int] = None, batch_id: Optional[int] = None,
               q: str = ""):
    query = db.query(CourseEnrolment, Course, User).join(
        Course, CourseEnrolment.course_id == Course.id).join(
        User, CourseEnrolment.student_id == User.id)
    if user.role == "faculty":
        query = query.filter(Course.lecturer_id == user.id)
    elif user.role == "student":
        query = query.filter(CourseEnrolment.student_id == user.id)
    elif user.role != "admin":
        raise HTTPException(403, "Not allowed")
    if status:
        query = query.filter(CourseEnrolment.status == status)
    if course_id:
        query = query.filter(Course.id == course_id)
    if batch_id:
        query = query.filter(CourseEnrolment.batch_id == batch_id)
    if q:
        query = query.filter(or_(User.name.ilike(f"%{q}%"), User.index_number.ilike(f"%{q}%"),
                                 Course.code.ilike(f"%{q}%")))
    rows = query.order_by(CourseEnrolment.requested_at.desc()).all()
    result = [_enrolment_dict(e, c, s, db) for e, c, s in rows]
    result.sort(key=lambda r: natural_key(r["index_number"]))
    return result


@router.patch("/academic/enrolments/{enrolment_id}")
def review(enrolment_id: int, body: Review,
           user: User = Depends(require_roles("faculty", "admin")), db: Session = Depends(get_db)):
    e = db.query(CourseEnrolment).filter(CourseEnrolment.id == enrolment_id).first()
    if not e:
        raise HTTPException(404, "Enrolment not found")
    c = db.query(Course).filter(Course.id == e.course_id).first()
    if user.role == "faculty" and c.lecturer_id != user.id:
        raise HTTPException(403, "Not your course")
    if body.status not in ("approved", "rejected"):
        raise HTTPException(400, "Status must be approved or rejected")
    e.status = body.status; e.reviewed_at = datetime.utcnow(); e.reviewed_by = user.id
    db.commit()
    audit(db, user, "review_enrolment", "course_enrolment", e.id, f"{c.code}: {body.status}")
    notify(db, e.student_id, f"Enrolment {body.status}",
           f"Your enrolment for {c.code} — {c.title} was {body.status}.",
           category="enrolment", link="/student/courses")
    publish_sync("enrolments", {"action": "review", "course_id": c.id, "status": body.status},
                 user_ids=[e.student_id], roles=["admin"])
    return {"message": f"Enrolment {body.status}"}


# ═══════════════════════════════ Settings ═══════════════════════════════════
DEFAULT_SETTINGS = {
    "auto_approve_students": "false",
    "default_enrolment_approval": "true",
    "attendance_session_minutes": "10",
    "attendance_gps_radius_meters": "50",
    "max_credits_per_semester": "24",
}


def _ensure_settings(db: Session):
    for k, v in DEFAULT_SETTINGS.items():
        if not db.query(SystemSetting).filter_by(key=k).first():
            db.add(SystemSetting(key=k, value=v))
    db.commit()


@router.get("/admin/settings")
def get_settings(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    _ensure_settings(db)
    vals = {x.key: x.value for x in db.query(SystemSetting).all()}
    return {
        "auto_approve_students": vals.get("auto_approve_students") == "true",
        "default_enrolment_approval": vals.get("default_enrolment_approval") == "true",
        "attendance_session_minutes": int(vals.get("attendance_session_minutes", "10")),
        "attendance_gps_radius_meters": int(vals.get("attendance_gps_radius_meters", "50")),
        "max_credits_per_semester": int(vals.get("max_credits_per_semester", "24")),
    }


@router.put("/admin/settings")
def save_settings(body: SettingsBody, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    for k, v in body.model_dump().items():
        row = db.query(SystemSetting).filter_by(key=k).first()
        value = str(v).lower() if isinstance(v, bool) else str(v)
        if row:
            row.value = value
        else:
            db.add(SystemSetting(key=k, value=value))
    db.commit()
    audit(db, user, "update", "settings", "", "Platform settings updated")
    publish_sync("settings", body.model_dump(), roles=["admin", "faculty", "student"])
    return {"message": "Settings saved", **body.model_dump()}


# ═══════════════════════════════ Timetable ══════════════════════════════════
class TimetableBody(BaseModel):
    course_id: int
    batch_id: Optional[int] = None
    faculty_id: Optional[int] = None
    day_of_week: int = Field(ge=0, le=5)
    period: str
    section: Optional[str] = None
    class_type: Optional[str] = "theory"
    room_no: Optional[str] = None
    venue_id: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    academic_session_id: Optional[int] = None
    is_published: bool = False


def _slot_dict(s: FacultySchedule, db: Session):
    f = db.query(User).filter(User.id == s.faculty_id).first()
    course = db.query(Course).filter(Course.id == s.course_id).first() if s.course_id else None
    venue = db.query(Venue).filter(Venue.id == s.venue_id).first() if s.venue_id else None
    batch = db.query(CourseBatch).filter(CourseBatch.id == s.batch_id).first() if s.batch_id else None
    return {
        "id": s.id, "faculty_id": s.faculty_id, "faculty_name": f.name if f else None,
        "day_of_week": s.day_of_week,
        "day_name": DAY_NAMES[s.day_of_week] if 0 <= s.day_of_week <= 5 else None,
        "period": s.period, "subject": s.subject, "subject_code": s.subject_code,
        "class_type": s.class_type, "room_no": s.room_no,
        "start_time": s.start_time, "end_time": s.end_time,
        "course_id": s.course_id, "course_title": course.title if course else s.subject,
        "course_code": course.code if course else s.subject_code,
        "batch_id": s.batch_id, "batch_name": batch.name if batch else None,
        "venue_id": s.venue_id, "venue_name": venue.name if venue else None,
        "academic_session_id": s.academic_session_id, "is_published": s.is_published,
    }


def _validate_slot(db: Session, body: TimetableBody, exclude_id: Optional[int] = None):
    if body.period not in ALL_PERIODS:
        raise HTTPException(400, f"Period must be one of {', '.join(ALL_PERIODS)}")
    course = db.query(Course).filter(Course.id == body.course_id).first()
    if not course:
        raise HTTPException(404, "Course not found — create the course before adding it to the timetable")

    batch = None
    if body.batch_id is not None:
        batch = db.query(CourseBatch).filter(CourseBatch.id == body.batch_id).first()
        if not batch or batch.course_id != course.id:
            raise HTTPException(400, "The selected batch does not belong to this course")

    faculty_id = body.faculty_id or (batch.lecturer_id if batch else None) or course.lecturer_id
    faculty = db.query(User).filter(User.id == faculty_id, User.role == "faculty").first()
    if not faculty:
        raise HTTPException(404, "Lecturer not found")

    start = _hhmm(body.start_time) if body.start_time else None
    end = _hhmm(body.end_time) if body.end_time else None
    default_start, default_end = PERIOD_TIMES[body.period]
    start = start or _hhmm(default_start)
    end = end or _hhmm(default_end)
    if start >= end:
        raise HTTPException(400, "End time must be later than the start time")

    if body.venue_id and not db.query(Venue).filter(Venue.id == body.venue_id).first():
        raise HTTPException(404, "Venue not found")

    q = db.query(FacultySchedule).filter(FacultySchedule.day_of_week == body.day_of_week,
                                         FacultySchedule.period == body.period)
    if exclude_id:
        q = q.filter(FacultySchedule.id != exclude_id)

    if q.filter(FacultySchedule.faculty_id == faculty_id).first():
        raise HTTPException(409, "This lecturer already has a class in that day/period")
    if body.batch_id and q.filter(FacultySchedule.batch_id == body.batch_id).first():
        raise HTTPException(409, "This batch already has a class in that day/period")
    if body.section and q.filter(FacultySchedule.section == body.section).first():
        raise HTTPException(409, f"Section {body.section} already has a class in that day/period")
    if body.venue_id and q.filter(FacultySchedule.venue_id == body.venue_id).first():
        raise HTTPException(409, f"{_venue_name(db, body.venue_id) or 'This venue'} is already booked in that day/period")

    if body.section:
        same_day = q.filter(FacultySchedule.section == body.section,
                            FacultySchedule.day_of_week == body.day_of_week).all()
        for slot in same_day:
            s2 = _hhmm(slot.start_time); e2 = _hhmm(slot.end_time)
            if s2 and e2 and start < e2 and s2 < end:
                raise HTTPException(409, "This time range overlaps another class for the same section")
    return course, faculty_id, start, end


def _apply_slot(row: FacultySchedule, body: TimetableBody, course: Course, faculty_id: int,
                start: datetime, end: datetime, db: Session):
    row.faculty_id = faculty_id
    row.day_of_week = body.day_of_week
    row.period = body.period
    row.course_id = course.id
    row.batch_id = body.batch_id
    row.subject = course.title
    row.subject_code = course.code
    row.section = (body.section or "").strip() or None
    row.class_type = (body.class_type or "theory").strip()
    row.venue_id = body.venue_id
    row.room_no = (body.room_no or "").strip() or _venue_name(db, body.venue_id) or course.code
    row.start_time = start.strftime("%H:%M")
    row.end_time = end.strftime("%H:%M")
    row.academic_session_id = body.academic_session_id
    row.is_published = body.is_published


@router.get("/admin/timetable")
def list_timetable(user: User = Depends(require_admin), db: Session = Depends(get_db),
                   day: Optional[int] = None, published: Optional[bool] = None,
                   faculty_id: Optional[int] = None, venue_id: Optional[int] = None):
    q = db.query(FacultySchedule)
    if day is not None:
        q = q.filter(FacultySchedule.day_of_week == day)
    if published is not None:
        q = q.filter(FacultySchedule.is_published == published)
    if faculty_id:
        q = q.filter(FacultySchedule.faculty_id == faculty_id)
    if venue_id:
        q = q.filter(FacultySchedule.venue_id == venue_id)
    rows = q.order_by(FacultySchedule.day_of_week, FacultySchedule.period).all()
    return [_slot_dict(s, db) for s in rows]


@router.post("/admin/timetable", status_code=201)
def create_slot(body: TimetableBody, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    course, faculty_id, start, end = _validate_slot(db, body)
    row = FacultySchedule()
    _apply_slot(row, body, course, faculty_id, start, end, db)
    db.add(row); db.commit(); db.refresh(row)
    audit(db, user, "create", "timetable", row.id,
          f"{course.code} {DAY_NAMES[body.day_of_week]} {body.period}")
    publish_sync("timetable", {"action": "create", "slot_id": row.id}, roles=["admin", "faculty"])
    return _slot_dict(row, db)


@router.put("/admin/timetable/{slot_id}")
def update_slot(slot_id: int, body: TimetableBody, user: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    row = db.query(FacultySchedule).filter(FacultySchedule.id == slot_id).first()
    if not row:
        raise HTTPException(404, "Timetable entry not found")
    course, faculty_id, start, end = _validate_slot(db, body, exclude_id=slot_id)
    _apply_slot(row, body, course, faculty_id, start, end, db)
    db.commit(); db.refresh(row)
    audit(db, user, "update", "timetable", row.id,
          f"{course.code} {DAY_NAMES[body.day_of_week]} {body.period}")
    publish_sync("timetable", {"action": "update", "slot_id": row.id}, roles=["admin", "faculty"])
    return _slot_dict(row, db)


@router.delete("/admin/timetable/{slot_id}")
def delete_slot(slot_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.query(FacultySchedule).filter(FacultySchedule.id == slot_id).first()
    if not row:
        raise HTTPException(404, "Timetable entry not found")
    db.delete(row); db.commit()
    audit(db, user, "delete", "timetable", slot_id)
    publish_sync("timetable", {"action": "delete", "slot_id": slot_id}, roles=["admin", "faculty"])
    return {"message": "Timetable entry deleted"}


class PublishBody(BaseModel):
    publish: bool = True
    academic_session_id: Optional[int] = None
    day_of_week: Optional[int] = None


@router.post("/admin/timetable/publish")
def publish_timetable(body: PublishBody, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    q = db.query(FacultySchedule)
    if body.academic_session_id:
        q = q.filter(FacultySchedule.academic_session_id == body.academic_session_id)
    if body.day_of_week is not None:
        q = q.filter(FacultySchedule.day_of_week == body.day_of_week)
    rows = q.all()
    if not rows:
        raise HTTPException(404, "No timetable entries match those filters")
    for r in rows:
        r.is_published = body.publish
    db.commit()
    audit(db, user, "publish" if body.publish else "unpublish", "timetable", "", f"{len(rows)} entries")
    student_ids = [u.id for u in db.query(User).filter(User.role == "student",
                                                       User.is_approved == True).all()]
    faculty_ids = [u.id for u in db.query(User).filter(User.role == "faculty").all()]
    title = "Timetable published" if body.publish else "Timetable updated"
    notify_many(db, student_ids + faculty_ids, title,
                "The class timetable is now available in your portal.",
                category="timetable", link="/student/dashboard")
    publish_sync("timetable", {"action": "publish" if body.publish else "unpublish", "count": len(rows)},
                 roles=["admin", "faculty", "student"])
    return {"message": f"{len(rows)} timetable entries {'published' if body.publish else 'set to draft'}",
            "count": len(rows), "published": body.publish}


# ── Student timetable (published only) ───────────────────────────────────────
def _student_slots(user: User, db: Session, day: Optional[int] = None):
    """Published slots for the courses (and batches) the student is enrolled in.

    A student sees a class only when they hold an approved enrolment for the
    slot's course, and — when the slot targets a specific batch — only for the
    batch they selected. Legacy slots without a batch fall back to a course match.
    """
    enrolments = db.query(CourseEnrolment).filter(
        CourseEnrolment.student_id == user.id,
        CourseEnrolment.status == "approved").all()
    if not enrolments:
        return []
    by_course = {e.course_id: e for e in enrolments}
    q = db.query(FacultySchedule).filter(
        FacultySchedule.is_published == True,
        FacultySchedule.course_id.in_(list(by_course.keys())))
    if day is not None:
        q = q.filter(FacultySchedule.day_of_week == day)
    slots = q.order_by(FacultySchedule.day_of_week, FacultySchedule.period).all()
    result = []
    for s in slots:
        enrolment = by_course.get(s.course_id)
        # A batch-scoped slot is visible only to students in that batch.
        if s.batch_id and enrolment and enrolment.batch_id != s.batch_id:
            continue
        result.append(s)
    return result


@router.get("/student/timetable")
def student_timetable(day: Optional[int] = None, user: User = Depends(require_roles("student")),
                      db: Session = Depends(get_db)):
    rows = _student_slots(user, db, day)
    result = []
    for s in rows:
        d = _slot_dict(s, db)
        d["is_free"] = False
        result.append(d)
    return result


@router.get("/student/timetable/week")
def student_timetable_week(user: User = Depends(require_roles("student")), db: Session = Depends(get_db)):
    slots = student_timetable(None, user, db)
    week = {DAY_NAMES[i]: [] for i in range(6)}
    for s in slots:
        week[DAY_NAMES[s["day_of_week"]]].append(s)
    return week


@router.get("/student/my-courses")
def student_my_courses(user: User = Depends(require_roles("student")), db: Session = Depends(get_db)):
    """The student's approved course list — sourced from enrolment records only."""
    rows = db.query(CourseEnrolment, Course).join(
        Course, CourseEnrolment.course_id == Course.id).filter(
        CourseEnrolment.student_id == user.id,
        CourseEnrolment.status == "approved").all()
    out = []
    for e, c in rows:
        batch = db.query(CourseBatch).filter(CourseBatch.id == e.batch_id).first() if e.batch_id else None
        lecturer = db.query(User).filter(User.id == c.lecturer_id).first()
        schedule_rows = db.query(FacultySchedule).filter(
            FacultySchedule.course_id == c.id, FacultySchedule.is_published == True).order_by(
            FacultySchedule.day_of_week, FacultySchedule.start_time).all()
        schedules = [_slot_dict(slot, db) for slot in schedule_rows
                     if not slot.batch_id or slot.batch_id == e.batch_id]
        out.append({
            "enrolment_id": e.id, "course_id": c.id, "code": c.code, "title": c.title,
            "description": c.description, "credit_hours": c.credit_hours, "level": c.level,
            "semester": c.semester, "batch_id": e.batch_id,
            "batch_name": batch.name if batch else None,
            "enrolment_status": e.status,
            "lecturer_id": lecturer.id if lecturer else None,
            "lecturer_name": lecturer.name if lecturer else None,
            "batches": [_batch_dict(b, db, with_counts=True) for b in _course_batches(db, c.id, active_only=True)],
            "schedules": schedules,
        })
    out.sort(key=lambda r: (r["code"] or ""))
    return out


# ── Lecturer course list, class list and materials ───────────────────────────
@router.get("/faculty/my-courses")
def my_courses(user: User = Depends(require_roles("faculty")), db: Session = Depends(get_db)):
    rows = db.query(Course).filter(Course.lecturer_id == user.id).order_by(Course.code).all()
    out = []
    for c in rows:
        enrolled = db.query(CourseEnrolment).filter(CourseEnrolment.course_id == c.id,
                                                    CourseEnrolment.status == "approved").count()
        pending = db.query(CourseEnrolment).filter(CourseEnrolment.course_id == c.id,
                                                   CourseEnrolment.status == "pending").count()
        schedules = [_slot_dict(slot, db) for slot in db.query(FacultySchedule).filter(
            FacultySchedule.course_id == c.id).order_by(FacultySchedule.day_of_week, FacultySchedule.start_time).all()]
        out.append({**serialize_course(c, db, user, include_prereqs=True),
                    "enrolled_count": enrolled, "pending_count": pending,
                    "schedules": schedules,
                    "batches": [_batch_dict(b, db, with_counts=True) for b in _course_batches(db, c.id)]})
    return out


@router.get("/faculty/class-list")
def class_list(user: User = Depends(require_roles("faculty")), db: Session = Depends(get_db),
               course_id: Optional[int] = None, batch_id: Optional[int] = None):
    """Students enrolled in a lecturer's course, optionally filtered to a batch.

    Students are sorted by their institutional index number using natural
    (alphanumeric) ordering.
    """
    q = db.query(Course).filter(Course.lecturer_id == user.id)
    if course_id:
        q = q.filter(Course.id == course_id)
    result = []
    for c in q.all():
        batches = _course_batches(db, c.id)
        batch_names = {b.id: b.name for b in batches}
        rows = db.query(CourseEnrolment, User).join(
            User, CourseEnrolment.student_id == User.id).filter(
            CourseEnrolment.course_id == c.id, CourseEnrolment.status == "approved").all()
        students = []
        for e, s in rows:
            if batch_id and e.batch_id != batch_id:
                continue
            students.append({"id": s.id, "name": s.name, "index_number": s.index_number,
                             "email": s.email, "programme": s.department, "level": s.level,
                             "batch_id": e.batch_id, "batch_name": batch_names.get(e.batch_id)})
        students.sort(key=lambda s: natural_key(s["index_number"]))
        result.append({
            "course_id": c.id, "course_code": c.code, "course_title": c.title,
            "batches": [_batch_dict(b, db, with_counts=True) for b in batches],
            "students": students,
        })
    return result


class MaterialBody(BaseModel):
    course_id: int
    title: str = Field(min_length=2)
    description: Optional[str] = None
    url: Optional[str] = None
    material_type: Optional[str] = "link"


class MaterialUpdateBody(BaseModel):
    title: str = Field(min_length=2)
    description: Optional[str] = None
    url: Optional[str] = None
    material_type: Optional[str] = "link"


@router.get("/academic/materials")
def list_materials(user: User = Depends(get_current_user), db: Session = Depends(get_db),
                   course_id: Optional[int] = None):
    q = db.query(LearningMaterial)
    if user.role == "student":
        approved = [e.course_id for e in db.query(CourseEnrolment).filter(
            CourseEnrolment.student_id == user.id, CourseEnrolment.status == "approved").all()]
        q = q.filter(LearningMaterial.course_id.in_(approved or [-1]))
    elif user.role == "faculty":
        mine = [c.id for c in db.query(Course).filter(Course.lecturer_id == user.id).all()]
        q = q.filter(LearningMaterial.course_id.in_(mine or [-1]))
    if course_id:
        q = q.filter(LearningMaterial.course_id == course_id)
    rows = q.order_by(LearningMaterial.created_at.desc()).all()
    out = []
    for m in rows:
        c = db.query(Course).filter(Course.id == m.course_id).first()
        out.append({"id": m.id, "course_id": m.course_id, "course_code": c.code if c else None,
                    "course_title": c.title if c else None, "title": m.title,
                    "description": m.description, "url": m.url, "material_type": m.material_type,
                    "created_at": m.created_at.isoformat()})
    return out


@router.post("/academic/materials", status_code=201)
def create_material(body: MaterialBody, user: User = Depends(require_roles("faculty", "admin")),
                    db: Session = Depends(get_db)):
    c = db.query(Course).filter(Course.id == body.course_id).first()
    if not c:
        raise HTTPException(404, "Course not found")
    if user.role == "faculty" and c.lecturer_id != user.id:
        raise HTTPException(403, "You can only add materials to your own courses")
    m = LearningMaterial(course_id=c.id, title=body.title.strip(), description=body.description,
                         url=body.url, material_type=body.material_type or "link", uploaded_by=user.id)
    db.add(m); db.commit(); db.refresh(m)
    audit(db, user, "create", "material", m.id, f"{c.code}: {m.title}")
    student_ids = [e.student_id for e in db.query(CourseEnrolment).filter(
        CourseEnrolment.course_id == c.id, CourseEnrolment.status == "approved").all()]
    notify_many(db, student_ids, "New learning material", f"{c.code}: {m.title}",
                category="material", link="/student/courses")
    publish_sync("materials", {"action": "create", "course_id": c.id}, user_ids=student_ids,
                 roles=["admin"])
    return {"id": m.id, "course_id": c.id, "title": m.title, "url": m.url,
            "material_type": m.material_type}


@router.put("/academic/materials/{material_id}")
def update_material(material_id: int, body: MaterialUpdateBody,
                    user: User = Depends(require_roles("faculty", "admin")),
                    db: Session = Depends(get_db)):
    m = db.query(LearningMaterial).filter(LearningMaterial.id == material_id).first()
    if not m:
        raise HTTPException(404, "Material not found")
    c = db.query(Course).filter(Course.id == m.course_id).first()
    if user.role == "faculty" and c and c.lecturer_id != user.id:
        raise HTTPException(403, "You can only edit materials on your own courses")
    m.title = body.title.strip()
    m.description = body.description
    m.url = body.url
    m.material_type = body.material_type or "link"
    db.commit(); db.refresh(m)
    audit(db, user, "update", "material", m.id, f"{c.code if c else ''}: {m.title}")
    student_ids = [e.student_id for e in db.query(CourseEnrolment).filter(
        CourseEnrolment.course_id == m.course_id, CourseEnrolment.status == "approved").all()]
    publish_sync("materials", {"action": "update", "course_id": m.course_id},
                 user_ids=student_ids, roles=["admin"])
    return {"id": m.id, "course_id": m.course_id, "title": m.title, "url": m.url,
            "material_type": m.material_type}


@router.delete("/academic/materials/{material_id}")
def delete_material(material_id: int, user: User = Depends(require_roles("faculty", "admin")),
                    db: Session = Depends(get_db)):
    m = db.query(LearningMaterial).filter(LearningMaterial.id == material_id).first()
    if not m:
        raise HTTPException(404, "Material not found")
    c = db.query(Course).filter(Course.id == m.course_id).first()
    if user.role == "faculty" and c and c.lecturer_id != user.id:
        raise HTTPException(403, "You can only remove materials from your own courses")
    db.delete(m); db.commit()
    audit(db, user, "delete", "material", material_id, m.title)
    return {"message": "Material removed"}


# ── Attendance register & reports (course-aware) ─────────────────────────────
@router.get("/faculty/attendance-register")
def attendance_register(user: User = Depends(require_roles("faculty", "admin")),
                        db: Session = Depends(get_db), course_id: Optional[int] = None,
                        date_from: Optional[str] = None, date_to: Optional[str] = None,
                        status: Optional[str] = None, q: str = ""):
    query = db.query(Attendance, User, Course).join(
        User, Attendance.student_id == User.id).outerjoin(Course, Attendance.course_id == Course.id)
    if user.role == "faculty":
        query = query.filter(Attendance.faculty_id == user.id)
    if course_id:
        query = query.filter(Attendance.course_id == course_id)
    if date_from:
        query = query.filter(Attendance.date >= date_from)
    if date_to:
        query = query.filter(Attendance.date <= date_to)
    if status:
        query = query.filter(Attendance.status == status)
    if q:
        query = query.filter(or_(User.name.ilike(f"%{q}%"), User.index_number.ilike(f"%{q}%")))
    rows = query.order_by(Attendance.marked_at.desc()).all()
    return [{"id": a.id, "student_id": s.id, "student_name": s.name, "index_number": s.index_number,
             "email": s.email, "department": s.department, "level": s.level, "faculty_id": a.faculty_id,
             "course_id": a.course_id, "course_title": c.title if c else None,
             "course_code": c.code if c else None, "date": a.date, "period": a.period,
             "status": a.status, "marked_by": a.marked_by,
             "timestamp": a.marked_at.isoformat() if a.marked_at else None}
            for a, s, c in rows]


@router.get("/admin/attendance-summary")
def attendance_summary(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    courses = db.query(Course).order_by(Course.code).all()
    out = []
    for c in courses:
        records = db.query(Attendance).filter(Attendance.course_id == c.id).all()
        present = sum(1 for r in records if r.status == "present")
        total = len(records)
        lecturer = db.query(User).filter(User.id == c.lecturer_id).first()
        out.append({"course_id": c.id, "code": c.code, "title": c.title,
                    "lecturer_name": lecturer.name if lecturer else None,
                    "records": total, "present": present,
                    "rate": round((present / total) * 100, 1) if total else None,
                    "enrolled": db.query(CourseEnrolment).filter(
                        CourseEnrolment.course_id == c.id,
                        CourseEnrolment.status == "approved").count()})
    return out
