"""Admin CRUD (students, faculty, courses, timetable, attendance) + password change.

Read (GET) endpoints for these resources live in main.py; this router adds
create / update / delete and is included from main.py.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import User, FacultySchedule, QRSession, Attendance, NEPCourse, CourseEnrolment, Course, Programme, Department, RegistrationPayment, AttendanceSession
from seed import PERIOD_TIMES, ALL_PERIODS
from utils import hash_password, verify_password
from storage import delete_selfie

router = APIRouter()


def admin_only(cu: User = Depends(get_current_user)) -> User:
    if cu.role != "admin":
        raise HTTPException(403, "Administrator access required")
    return cu


def _email_taken(db: Session, email: str, exclude_id: Optional[int] = None) -> bool:
    q = db.query(User).filter(User.email.ilike(email))
    if exclude_id:
        q = q.filter(User.id != exclude_id)
    return q.first() is not None


def _get_user(db: Session, user_id: int, role: str) -> User:
    u = db.query(User).filter(User.id == user_id, User.role == role).first()
    if not u:
        raise HTTPException(404, f"{role.capitalize()} not found")
    return u


def _clean(value: Optional[str]) -> Optional[str]:
    return value.strip() if isinstance(value, str) else value


# ═════════════════════════ Students ═════════════════════════
class StudentCreate(BaseModel):
    name: str = Field(min_length=1)
    index_number: str = Field(min_length=3)
    email: str = Field(min_length=3)
    password: str = Field(min_length=6)
    programme_id: Optional[int] = None
    institution_name: str = Field(min_length=2, max_length=180)
    faculty_name: Optional[str] = None
    department: Optional[str] = None
    programme_name: Optional[str] = None
    academic_year: Optional[str] = None
    level: Optional[int] = Field(default=100, ge=100, le=700)
    interests: Optional[str] = ""
    is_approved: bool = True


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    index_number: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=6)
    programme_id: Optional[int] = None
    institution_name: Optional[str] = None
    faculty_name: Optional[str] = None
    department: Optional[str] = None
    programme_name: Optional[str] = None
    academic_year: Optional[str] = None
    level: Optional[int] = Field(default=None, ge=100, le=700)
    interests: Optional[str] = None
    is_approved: Optional[bool] = None


def _student_dict(u: User, db: Session = None):
    programme = db.query(Programme).filter(Programme.id == u.programme_id).first() if (db and u.programme_id) else None
    department = db.query(Department).filter(Department.id == u.department_id).first() if (db and u.department_id) else None
    return {"id": u.id, "name": u.name, "email": u.email, "index_number": u.index_number,
            "institution_name": u.institution_name, "faculty_name": u.faculty_name,
            "department": department.name if department else u.department,
            "programme_id": u.programme_id, "programme_name": programme.name if programme else u.programme_name,
            "academic_year": u.academic_year, "level": u.level, "interests": u.interests,
            "identity_status": u.identity_status, "has_registration_selfie": bool(u.registration_photo_ref),
            "ghana_card_last4": u.ghana_card_last4, "is_approved": u.is_approved}


def _resolve_student_scope(db: Session, programme_id: Optional[int]):
    """Return (programme, department) for a chosen programme, or (None, None)."""
    if not programme_id:
        return None, None
    programme = db.query(Programme).filter(Programme.id == programme_id).first()
    if not programme:
        raise HTTPException(404, "Select a valid academic programme")
    department = db.query(Department).filter(Department.id == programme.department_id).first() if programme.department_id else None
    return programme, department


def _delete_student(db: Session, s: User):
    if s.registration_photo_ref:
        delete_selfie(s.registration_photo_ref)
    db.query(Attendance).filter(Attendance.student_id == s.id).delete()
    db.delete(s)
    db.commit()


@router.post("/admin/students", status_code=201)
def create_student(body: StudentCreate, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if _email_taken(db, email):
        raise HTTPException(409, "Email already registered")
    index_number=body.index_number.strip().upper()
    if db.query(User).filter(User.index_number==index_number).first(): raise HTTPException(409,"Index number already registered")
    programme, department = _resolve_student_scope(db, body.programme_id)
    s = User(name=body.name.strip(), index_number=index_number, email=email, password=hash_password(body.password),
             role="student",
             programme_id=(programme.id if programme else None),
             department_id=(programme.department_id if programme else None),
             institution_name=_clean(body.institution_name), faculty_name=_clean(body.faculty_name),
             department=_clean(body.department) or (department.name if department else None),
             programme_name=_clean(body.programme_name) or (programme.name if programme else None),
             academic_year=_clean(body.academic_year), level=body.level or 100,
             interests=_clean(body.interests), is_approved=body.is_approved,
             identity_status="verified" if body.is_approved else "pending")
    db.add(s); db.commit(); db.refresh(s)
    return _student_dict(s, db)


@router.put("/admin/students/{student_id}")
def update_student(student_id: int, body: StudentUpdate, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    s = _get_user(db, student_id, "student")
    if body.email is not None:
        email = body.email.strip().lower()
        if _email_taken(db, email, s.id):
            raise HTTPException(409, "Email already registered")
        s.email = email
    if body.name is not None and body.name.strip():
        s.name = body.name.strip()
    if body.index_number is not None:
        number=body.index_number.strip().upper()
        duplicate=db.query(User).filter(User.index_number==number,User.id!=s.id).first()
        if duplicate: raise HTTPException(409,"Index number already registered")
        s.index_number=number
    if body.password:
        s.password = hash_password(body.password)
    if body.programme_id is not None:
        programme, department = _resolve_student_scope(db, body.programme_id)
        s.programme_id = programme.id
        s.department_id = programme.department_id
        s.department = department.name if department else None
    for field in ("institution_name", "faculty_name", "department", "programme_name", "academic_year"):
        value = getattr(body, field)
        if value is not None:
            setattr(s, field, _clean(value))
    if body.level is not None:
        s.level = body.level
    if body.interests is not None:
        s.interests = body.interests.strip()
    if body.is_approved is not None:
        s.is_approved = body.is_approved
    db.commit(); db.refresh(s)
    return _student_dict(s, db)


@router.delete("/admin/students/{student_id}")
def delete_student(student_id: int, force: bool = False, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    student=_get_user(db, student_id, "student")
    history=db.query(Attendance).filter(Attendance.student_id==student.id).count()
    enrolments=db.query(CourseEnrolment).filter(CourseEnrolment.student_id==student.id).count()
    if (history or enrolments) and not force:
        raise HTTPException(409, f"Student has {history} attendance record(s) and {enrolments} course enrolment(s). Repeat with force=true only if permanent deletion is intended.")
    db.query(CourseEnrolment).filter(CourseEnrolment.student_id==student.id).delete()
    _delete_student(db, student)
    return {"message": "Student deleted"}


@router.post("/admin/reject/{student_id}")
def reject_student(student_id: int, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    s = _get_user(db, student_id, "student")
    if s.is_approved:
        raise HTTPException(400, "Student is already approved; use delete instead")
    _delete_student(db, s)
    return {"message": "Registration rejected and removed"}


# ═════════════════════════ Faculty ═════════════════════════
class FacultyCreate(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    password: str = Field(min_length=6)
    phone: Optional[str] = None
    staff_id: str = Field(min_length=2, max_length=40)
    institution_name: str = Field(min_length=2, max_length=180)
    faculty_name: Optional[str] = None
    department: Optional[str] = None
    programme_name: Optional[str] = None
    designation: Optional[str] = None
    is_approved: bool = True


class FacultyUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=6)
    phone: Optional[str] = None
    staff_id: Optional[str] = None
    institution_name: Optional[str] = None
    faculty_name: Optional[str] = None
    department: Optional[str] = None
    programme_name: Optional[str] = None
    designation: Optional[str] = None
    is_approved: Optional[bool] = None


def _faculty_dict(u: User):
    return {"id": u.id, "name": u.name, "email": u.email, "phone": u.phone,
            "staff_id": u.staff_id, "institution_name": u.institution_name,
            "faculty_name": u.faculty_name, "department": u.department,
            "programme_name": u.programme_name, "designation": u.designation,
            "identity_status": u.identity_status, "has_registration_selfie": bool(u.registration_photo_ref),
            "ghana_card_last4": u.ghana_card_last4, "is_approved": u.is_approved}


@router.post("/admin/faculty", status_code=201)
def create_faculty(body: FacultyCreate, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if _email_taken(db, email):
        raise HTTPException(409, "Email already registered")
    staff_id = _clean(body.staff_id)
    if staff_id and db.query(User).filter(User.staff_id == staff_id.upper()).first():
        raise HTTPException(409, "Staff ID already registered")
    f = User(name=body.name.strip(), email=email, password=hash_password(body.password),
             role="faculty", phone=_clean(body.phone), staff_id=staff_id.upper() if staff_id else None,
             institution_name=_clean(body.institution_name), faculty_name=_clean(body.faculty_name),
             department=_clean(body.department), programme_name=_clean(body.programme_name),
             designation=_clean(body.designation), is_approved=body.is_approved,
             identity_status="verified" if body.is_approved else "pending")
    db.add(f); db.commit(); db.refresh(f)
    return _faculty_dict(f)


@router.put("/admin/faculty/{faculty_id}")
def update_faculty(faculty_id: int, body: FacultyUpdate, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    f = _get_user(db, faculty_id, "faculty")
    if body.email is not None:
        email = body.email.strip().lower()
        if _email_taken(db, email, f.id):
            raise HTTPException(409, "Email already registered")
        f.email = email
    if body.name is not None and body.name.strip():
        f.name = body.name.strip()
    previous_institution = f.institution_name
    if body.password:
        f.password = hash_password(body.password)
    if body.staff_id is not None:
        staff_id = body.staff_id.strip().upper()
        duplicate = db.query(User).filter(User.staff_id == staff_id, User.id != f.id).first()
        if duplicate: raise HTTPException(409, "Staff ID already registered")
        f.staff_id = staff_id or None
    for field in ("phone", "institution_name", "faculty_name", "department", "programme_name", "designation"):
        value = getattr(body, field)
        if value is not None:
            setattr(f, field, _clean(value))
    if body.is_approved is not None:
        f.is_approved = body.is_approved
    if body.institution_name is not None and f.institution_name != previous_institution:
        db.query(Course).filter(Course.lecturer_id == f.id).update(
            {Course.institution_name: f.institution_name}, synchronize_session=False)
    db.commit(); db.refresh(f)
    return _faculty_dict(f)


@router.delete("/admin/faculty/{faculty_id}")
def delete_faculty(faculty_id: int, force: bool = False, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    f = _get_user(db, faculty_id, "faculty")
    marked = db.query(Attendance).filter(Attendance.faculty_id == f.id).count()
    assigned_courses = db.query(Course).filter(Course.lecturer_id == f.id).count()
    if assigned_courses:
        raise HTTPException(409, f"This lecturer is assigned to {assigned_courses} course(s). Reassign or delete those courses before deleting the lecturer.")
    if db.query(RegistrationPayment).filter(RegistrationPayment.user_id == f.id).count():
        raise HTTPException(409, "This lecturer has registration payment history. Keep the account for audit purposes or contact the database administrator.")
    if marked and not force:
        raise HTTPException(409, f"This faculty member has {marked} attendance record(s). "
                                 "Deleting will also delete those records.")
    db.query(Attendance).filter(Attendance.faculty_id == f.id).delete()
    db.query(QRSession).filter(QRSession.faculty_id == f.id).delete()
    db.query(FacultySchedule).filter(FacultySchedule.faculty_id == f.id).delete()
    db.query(AttendanceSession).filter(AttendanceSession.faculty_id == f.id).delete()
    if f.registration_photo_ref:
        delete_selfie(f.registration_photo_ref)
    db.delete(f)
    db.commit()
    return {"message": "Faculty deleted"}


# ═════════════════════════ Learning resources (external catalogue) ═══════
# This is the supplementary self-study catalogue, distinct from institutional
# courses. Institutional courses are managed by the academic router.
class CourseBody(BaseModel):
    title: str = Field(min_length=1)
    category: str = Field(min_length=1)
    skill_tag: str = Field(min_length=1)
    duration: str = Field(min_length=1)
    platform: Optional[str] = None
    description: Optional[str] = None


def _course_dict(c: NEPCourse):
    return {"id": c.id, "title": c.title, "category": c.category, "skill_tag": c.skill_tag,
            "duration": c.duration, "platform": c.platform, "description": c.description}


@router.post("/admin/resources", status_code=201)
def create_course(body: CourseBody, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    c = NEPCourse(**{k: _clean(v) for k, v in body.model_dump().items()})
    db.add(c); db.commit(); db.refresh(c)
    return _course_dict(c)


@router.put("/admin/resources/{course_id}")
def update_course(course_id: int, body: CourseBody, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    c = db.query(NEPCourse).filter(NEPCourse.id == course_id).first()
    if not c:
        raise HTTPException(404, "Resource not found")
    for k, v in body.model_dump().items():
        setattr(c, k, _clean(v))
    db.commit(); db.refresh(c)
    return _course_dict(c)


@router.delete("/admin/resources/{course_id}")
def delete_course(course_id: int, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    c = db.query(NEPCourse).filter(NEPCourse.id == course_id).first()
    if not c:
        raise HTTPException(404, "Resource not found")
    db.delete(c); db.commit()
    return {"message": "Resource deleted"}


# ═════════════════════════ Attendance ═════════════════════════
class AttendanceCreate(BaseModel):
    student_id: int
    faculty_id: int
    date: str                      # YYYY-MM-DD
    period: str
    status: str = "present"


class AttendanceUpdate(BaseModel):
    status: str


def _check_status(status: str):
    if status not in ("present", "absent"):
        raise HTTPException(400, "Status must be 'present' or 'absent'")


@router.post("/admin/attendance", status_code=201)
def create_attendance(body: AttendanceCreate, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    raise HTTPException(410, "Attendance can only be created through a live lecturer QR code and verified location.")
    _check_status(body.status)
    if body.period not in ALL_PERIODS:
        raise HTTPException(400, f"Period must be one of {', '.join(ALL_PERIODS)}")
    _get_user(db, body.student_id, "student"); _get_user(db, body.faculty_id, "faculty")
    if db.query(Attendance).filter(Attendance.student_id == body.student_id,
                                   Attendance.date == body.date, Attendance.period == body.period).first():
        raise HTTPException(409, "Attendance already exists for this student/date/period; edit it instead")
    a = Attendance(student_id=body.student_id, faculty_id=body.faculty_id, date=body.date,
                   period=body.period, status=body.status, marked_by="admin")
    db.add(a); db.commit(); db.refresh(a)
    return {"id": a.id}


@router.put("/admin/attendance/{attendance_id}")
def update_attendance(attendance_id: int, body: AttendanceUpdate, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    raise HTTPException(410, "Attendance status is not manually editable. Attendance is recorded through a live QR code and verified location.")
    _check_status(body.status)
    a = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not a:
        raise HTTPException(404, "Attendance record not found")
    a.status = body.status; a.marked_by = "admin"
    db.commit()
    return {"message": "Updated"}


@router.delete("/admin/attendance/{attendance_id}")
def delete_attendance(attendance_id: int, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    a = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not a:
        raise HTTPException(404, "Attendance record not found")
    db.delete(a); db.commit()
    return {"message": "Deleted"}


# ═════════════════════════ Own account ═════════════════════════
class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


@router.put("/me/password")
def change_my_password(body: PasswordChange, cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, cu.password):
        raise HTTPException(400, "Current password is incorrect")
    cu.password = hash_password(body.new_password)
    db.commit()
    return {"message": "Password changed"}
