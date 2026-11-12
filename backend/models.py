from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float, ForeignKey,
    UniqueConstraint, Text, Index,
)
from datetime import datetime
from database import Base


# ═══════════════════════════════════════════════════════════════════════════
# Academic structure
#
# Legacy academic data hierarchy (not an institution-owned platform):
#   Faculty → Department → Programme → Course
# Academic sessions (academic year + semester) and venues complete the
# structure that courses and timetable entries reference.
# ═══════════════════════════════════════════════════════════════════════════

class Faculty(Base):
    __tablename__ = "faculties"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String, nullable=False, index=True)
    code       = Column(String, nullable=True, index=True)
    institution_name = Column(String, nullable=False, index=True, default="University of Cape Coast")
    dean       = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Department(Base):
    __tablename__ = "departments"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String, nullable=False, index=True)
    code       = Column(String, nullable=True, index=True)
    institution_name = Column(String, nullable=False, index=True, default="University of Cape Coast")
    faculty_id = Column(Integer, ForeignKey("faculties.id"), nullable=True, index=True)
    head       = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("faculty_id", "name", name="uq_department_faculty_name"),)


class Programme(Base):
    __tablename__ = "programmes"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String, nullable=False, index=True)
    code          = Column(String, nullable=True, index=True)
    institution_name = Column(String, nullable=False, index=True, default="University of Cape Coast")
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    award         = Column(String, nullable=True)   # BSc / BA / MPhil …
    duration_years = Column(Integer, nullable=True, default=4)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("department_id", "name", name="uq_programme_department_name"),)


class Venue(Base):
    __tablename__ = "venues"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String, nullable=False, unique=True, index=True)
    building   = Column(String, nullable=True)
    capacity   = Column(Integer, nullable=True)
    venue_type = Column(String, nullable=True, default="lecture")  # lecture | lab | seminar
    is_active  = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AcademicSession(Base):
    """An academic year + semester window (e.g. 2025/2026 First Semester)."""
    __tablename__ = "academic_sessions"

    id                 = Column(Integer, primary_key=True, index=True)
    academic_year      = Column(String, nullable=False, index=True)   # "2025/2026"
    semester           = Column(String, nullable=False)               # "First Semester"
    registration_open  = Column(Boolean, default=False, nullable=False)
    registration_start = Column(String, nullable=True)                # YYYY-MM-DD
    registration_end   = Column(String, nullable=True)                # YYYY-MM-DD
    is_current         = Column(Boolean, default=False, nullable=False)
    created_at         = Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("academic_year", "semester", name="uq_session_year_semester"),)


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String,  nullable=False)
    email           = Column(String,  unique=True, nullable=False, index=True)
    index_number    = Column(String, unique=True, nullable=True, index=True)
    password        = Column(String,  nullable=False)
    role            = Column(String,  nullable=False)   # admin / faculty / student
    department      = Column(String,  nullable=True)
    institution_name = Column(String, nullable=True, index=True)
    faculty_name = Column(String, nullable=True)
    programme_name = Column(String, nullable=True)
    academic_year = Column(String, nullable=True)
    designation = Column(String, nullable=True)
    department_id   = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    programme_id    = Column(Integer, ForeignKey("programmes.id"), nullable=True, index=True)
    level           = Column(Integer, nullable=True)    # 100 / 200 / 300 / 400
    phone           = Column(String, nullable=True, index=True)
    staff_id        = Column(String, nullable=True, unique=True, index=True)
    ghana_card_hash = Column(String, nullable=True, unique=True, index=True)
    ghana_card_last4 = Column(String, nullable=True)
    identity_document_type = Column(String, nullable=True, default="ghana_card")
    identity_document_hash = Column(String, nullable=True, unique=True, index=True)
    identity_document_last4 = Column(String, nullable=True)
    registration_photo_ref = Column(String, nullable=True)
    biometric_method = Column(String, nullable=True)  # selfie | device_biometric | pending
    identity_status = Column(String, nullable=False, default="pending")  # pending | verified | rejected
    registration_fee_required = Column(Boolean, nullable=False, default=False)
    section         = Column(String,  nullable=True, default="AI-1A")
    is_approved     = Column(Boolean, default=False)
    interests       = Column(String,  nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)


class FacultySchedule(Base):
    __tablename__ = "faculty_schedule"

    id           = Column(Integer, primary_key=True, index=True)
    faculty_id   = Column(Integer, ForeignKey("users.id"), nullable=False)
    day_of_week  = Column(Integer, nullable=False)   # 0=Mon … 5=Sat
    period       = Column(String,  nullable=False)   # "P1" … "P6"
    subject      = Column(String,  nullable=False)
    subject_code = Column(String,  nullable=True)
    section      = Column(String,  nullable=True)
    class_type   = Column(String,  nullable=True)    # "theory" | "lab"
    room_no      = Column(String,  nullable=False)
    start_time   = Column(String,  nullable=False)   # "09:00"
    end_time     = Column(String,  nullable=False)   # "09:50"
    # Authoritative links — a timetable entry references the canonical course
    # and venue records instead of duplicating free-text values.
    course_id    = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)
    venue_id     = Column(Integer, ForeignKey("venues.id"), nullable=True, index=True)
    batch_id     = Column(Integer, ForeignKey("course_batches.id"), nullable=True, index=True)
    academic_session_id = Column(Integer, ForeignKey("academic_sessions.id"), nullable=True, index=True)
    is_published = Column(Boolean, default=False, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow, nullable=False)


class QRSession(Base):
    __tablename__ = "qr_sessions"

    id         = Column(Integer, primary_key=True, index=True)
    faculty_id = Column(Integer, nullable=False)
    date       = Column(String,  nullable=False)
    period     = Column(String,  nullable=False)
    is_active  = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    latitude   = Column(Float, nullable=True)
    longitude  = Column(Float, nullable=True)
    token      = Column(String, nullable=True, unique=True, index=True)
    course_id  = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)


class AttendanceSession(Base):
    """A single scheduled class meeting for a course batch.

    The lecturer opens a session (course → batch → scheduled class/period) and
    students submit a live selfie against it. Uniqueness of a student's
    submission is enforced per session, which correctly distinguishes different
    courses that may share a date and period.
    """
    __tablename__ = "attendance_sessions"
    id         = Column(Integer, primary_key=True, index=True)
    course_id  = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    batch_id   = Column(Integer, ForeignKey("course_batches.id"), nullable=True, index=True)
    faculty_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    schedule_id = Column(Integer, ForeignKey("faculty_schedule.id"), nullable=True, index=True)
    academic_session_id = Column(Integer, ForeignKey("academic_sessions.id"), nullable=True, index=True)
    date       = Column(String, nullable=False)     # YYYY-MM-DD
    period     = Column(String, nullable=False)
    topic      = Column(String, nullable=True)
    token      = Column(String, nullable=True, index=True)
    access_code = Column(String, nullable=True, unique=True, index=True)
    latitude   = Column(Float, nullable=True)
    longitude  = Column(Float, nullable=True)
    radius_meters = Column(Integer, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    is_open    = Column(Boolean, default=True, nullable=False)
    opened_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at  = Column(DateTime, nullable=True)


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("student_id", "attendance_session_id", name="uq_attendance_student_session"),
        Index("ix_attendance_session", "attendance_session_id"),
    )

    id         = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    faculty_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    attendance_session_id = Column(Integer, ForeignKey("attendance_sessions.id"), nullable=True, index=True)
    course_id  = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)
    batch_id   = Column(Integer, ForeignKey("course_batches.id"), nullable=True, index=True)
    academic_session_id = Column(Integer, ForeignKey("academic_sessions.id"), nullable=True)
    date       = Column(String,  nullable=False)
    period     = Column(String,  nullable=False)
    status     = Column(String,  nullable=False)   # present / absent
    method     = Column(String,  default="SELFIE")  # SELFIE | QR | ADMIN
    marked_by  = Column(String,  default="student")
    image_ref  = Column(String,  nullable=True)    # opaque stored-photo key, never a public URL
    image_sha256 = Column(String, nullable=True, index=True)
    latitude   = Column(Float, nullable=True)
    longitude  = Column(Float, nullable=True)
    gps_accuracy = Column(Float, nullable=True)
    distance_meters = Column(Float, nullable=True)
    note       = Column(String, nullable=True)
    marked_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
    attendance_points = Column(Float, nullable=True)


class AttendanceCorrection(Base):
    """Audited change to an attendance record; the original row is preserved."""
    __tablename__ = "attendance_corrections"
    id            = Column(Integer, primary_key=True, index=True)
    attendance_id = Column(Integer, ForeignKey("attendance.id"), nullable=False, index=True)
    previous_status = Column(String, nullable=True)
    new_status    = Column(String, nullable=False)
    reason        = Column(String, nullable=False)
    actor_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor_name    = Column(String, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)


class GradingBand(Base):
    """A configurable grade band (e.g. 70–100 = A)."""
    __tablename__ = "grading_bands"
    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String, nullable=False)      # grade letter / label
    min_score  = Column(Float, nullable=False)
    max_score  = Column(Float, nullable=False)
    grade_point = Column(Float, nullable=True)
    remark     = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Assessment(Base):
    """An assessment for a course batch (assignment, quiz, exam …)."""
    __tablename__ = "assessments"
    id         = Column(Integer, primary_key=True, index=True)
    course_id  = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    batch_id   = Column(Integer, ForeignKey("course_batches.id"), nullable=True, index=True)
    title      = Column(String, nullable=False)
    component  = Column(String, nullable=False, default="continuous")  # assignment/quiz/test/mid_sem/practical/final_exam
    max_score  = Column(Float, nullable=False, default=100)
    weight     = Column(Float, nullable=True)      # contribution to the component/final mark
    academic_session_id = Column(Integer, ForeignKey("academic_sessions.id"), nullable=True)
    is_released = Column(Boolean, default=False, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Result(Base):
    """A student's mark for one assessment."""
    __tablename__ = "results"
    __table_args__ = (UniqueConstraint("assessment_id", "student_id", name="uq_result_assessment_student"),)
    id            = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=False, index=True)
    student_id    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_id     = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    score         = Column(Float, nullable=True)
    grade         = Column(String, nullable=True)
    remark        = Column(String, nullable=True)
    is_released   = Column(Boolean, default=False, nullable=False)
    entered_by    = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ResultAudit(Base):
    """Audited change to a mark/grade."""
    __tablename__ = "result_audit"
    id         = Column(Integer, primary_key=True, index=True)
    result_id  = Column(Integer, ForeignKey("results.id"), nullable=False, index=True)
    previous_score = Column(Float, nullable=True)
    new_score  = Column(Float, nullable=True)
    reason     = Column(String, nullable=True)
    actor_id   = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Announcement(Base):
    """An announcement targeted at an audience (institution/faculty/dept/programme/course/batch/role)."""
    __tablename__ = "announcements"
    id         = Column(Integer, primary_key=True, index=True)
    title      = Column(String, nullable=False)
    body       = Column(Text, nullable=True)
    audience   = Column(String, nullable=False, default="all")  # all/faculty/department/programme/course/batch/lecturers/students
    faculty_id = Column(Integer, ForeignKey("faculties.id"), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    programme_id  = Column(Integer, ForeignKey("programmes.id"), nullable=True)
    course_id  = Column(Integer, ForeignKey("courses.id"), nullable=True)
    batch_id   = Column(Integer, ForeignKey("course_batches.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class NEPCourse(Base):
    __tablename__ = "nep_courses"

    id          = Column(Integer, primary_key=True, index=True)
    title       = Column(String, nullable=False)
    category    = Column(String, nullable=False)
    skill_tag   = Column(String, nullable=False)
    duration    = Column(String, nullable=False)
    platform    = Column(String, nullable=True)   # e.g. "NPTEL / Coursera"
    description = Column(String, nullable=True)   # short course description
class Course(Base):
    """The single canonical course record used by academic structure,
    timetable, lecturer allocation, enrolment and student views."""
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    code = Column(String, nullable=False, unique=True, index=True)
    description = Column(String, nullable=True)
    department = Column(String, nullable=True)
    institution_name = Column(String, nullable=True, index=True)
    programme_name = Column(String, nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    programme_id = Column(Integer, ForeignKey("programmes.id"), nullable=True, index=True)
    level = Column(String, nullable=True)
    semester = Column(String, nullable=True)
    academic_year = Column(String, nullable=True)
    credit_hours = Column(Integer, nullable=True, default=3)
    lecturer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    registration_code = Column(String, nullable=False, unique=True, index=True)
    registration_code_expires_at = Column(DateTime, nullable=True)
    registration_open = Column(Boolean, default=True, nullable=False)
    enrolment_requires_approval = Column(Boolean, default=True, nullable=False)
    is_published = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CoursePrerequisite(Base):
    __tablename__ = "course_prerequisites"
    __table_args__ = (UniqueConstraint("course_id", "prerequisite_course_id", name="uq_course_prerequisite"),)
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    prerequisite_course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)


class CourseProgramme(Base):
    """Many-to-many: which programmes a course is offered to.

    A course is always linked to at least its primary ``Course.programme_id``;
    this table allows a course to be shared across several programmes.
    """
    __tablename__ = "course_programmes"
    __table_args__ = (UniqueConstraint("course_id", "programme_id", name="uq_course_programme"),)
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    programme_id = Column(Integer, ForeignKey("programmes.id"), nullable=False, index=True)


class CourseBatch(Base):
    """A teaching group for a single course (e.g. Database Management Batch 1).

    Batches are created per course. Capacity is unlimited by default: a nullable
    ``capacity`` of NULL means no limit, and enrolment never rejects a student on
    capacity grounds unless an administrator explicitly sets a positive limit.
    """
    __tablename__ = "course_batches"
    __table_args__ = (UniqueConstraint("course_id", "name", name="uq_batch_course_name"),)
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    lecturer_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    capacity = Column(Integer, nullable=True)         # NULL = unlimited
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CourseEnrolment(Base):
    __tablename__ = "course_enrolments"
    __table_args__ = (UniqueConstraint("course_id", "student_id", name="uq_course_student"),)
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("course_batches.id"), nullable=True, index=True)
    status = Column(String, default="pending", nullable=False)   # pending/approved/rejected/withdrawn
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    withdrawn_at = Column(DateTime, nullable=True)
    withdrawal_reason = Column(String, nullable=True)


class EnrolmentHistory(Base):
    """Immutable log of enrolment events (register / withdraw / batch change)."""
    __tablename__ = "enrolment_history"
    id = Column(Integer, primary_key=True, index=True)
    enrolment_id = Column(Integer, ForeignKey("course_enrolments.id"), nullable=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("course_batches.id"), nullable=True)
    action = Column(String, nullable=False)   # registered / withdrawn / batch_changed / approved / rejected
    detail = Column(String, nullable=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class SystemSetting(Base):
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RegistrationPayment(Base):
    """Auditable lecturer registration payment; provider references are unique."""
    __tablename__ = "registration_payments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reference = Column(String, nullable=False, unique=True, index=True)
    amount_pesewas = Column(Integer, nullable=False)
    currency = Column(String, nullable=False, default="GHS")
    provider = Column(String, nullable=False, default="paystack")
    status = Column(String, nullable=False, default="initialized")  # initialized/paid/failed
    authorization_url = Column(String, nullable=True)
    provider_transaction_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    verified_at = Column(DateTime, nullable=True)


class LearningMaterial(Base):
    __tablename__ = "learning_materials"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("course_batches.id"), nullable=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    url = Column(String, nullable=True)
    material_type = Column(String, nullable=True, default="link")  # link | note | file
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    body = Column(String, nullable=True)
    category = Column(String, nullable=True, default="general")
    link = Column(String, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    actor_name = Column(String, nullable=True)
    action = Column(String, nullable=False)
    entity = Column(String, nullable=True)
    entity_id = Column(String, nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

