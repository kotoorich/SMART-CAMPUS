"""Assessments, marks/results, grading bands and announcements.

Lecturers create assessments for their courses (optionally scoped to a batch),
enter and release marks, and publish announcements. Students see only released
results for courses they are enrolled in. Administrators manage grading bands
and can also publish institution-wide announcements.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from deps import require_admin, require_roles
from models import (
    User, Course, CourseBatch, CourseEnrolment, Assessment, Result, ResultAudit,
    GradingBand, Announcement, AcademicSession,
)
from realtime import audit, notify, notify_many, publish_sync
from utils import natural_key

router = APIRouter()

COMPONENTS = ("assignment", "quiz", "test", "mid_sem", "practical", "project", "final_exam", "continuous")


def _grade_for(db: Session, score: Optional[float], max_score: Optional[float] = None):
    """Map a raw mark to a grade band using the mark as a percentage of the maximum."""
    if score is None:
        return None, None
    percentage = score
    if max_score and max_score > 0:
        percentage = (score / max_score) * 100
    band = db.query(GradingBand).filter(GradingBand.min_score <= percentage,
                                        GradingBand.max_score >= percentage).order_by(
        GradingBand.min_score.desc()).first()
    if not band:
        return None, None
    return band.name, band.remark


def _assessment_dict(a: Assessment, db: Session, with_counts: bool = False):
    course = db.query(Course).filter(Course.id == a.course_id).first()
    batch = db.query(CourseBatch).filter(CourseBatch.id == a.batch_id).first() if a.batch_id else None
    data = {
        "id": a.id, "course_id": a.course_id, "course_code": course.code if course else None,
        "course_title": course.title if course else None,
        "batch_id": a.batch_id, "batch_name": batch.name if batch else None,
        "title": a.title, "component": a.component, "max_score": a.max_score,
        "weight": a.weight, "is_released": a.is_released,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
    if with_counts:
        data["marks_entered"] = db.query(Result).filter(Result.assessment_id == a.id).count()
    return data


# ── Grading bands (admin) ────────────────────────────────────────────────────
class BandBody(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    min_score: float = Field(ge=0, le=100)
    max_score: float = Field(ge=0, le=100)
    grade_point: Optional[float] = Field(default=None, ge=0, le=5)
    remark: Optional[str] = None


@router.get("/admin/grading-bands")
def list_bands(user: User = Depends(require_roles("admin", "faculty")), db: Session = Depends(get_db)):
    rows = db.query(GradingBand).order_by(GradingBand.min_score.desc()).all()
    return [{"id": b.id, "name": b.name, "min_score": b.min_score, "max_score": b.max_score,
             "grade_point": b.grade_point, "remark": b.remark} for b in rows]


@router.post("/admin/grading-bands", status_code=201)
def create_band(body: BandBody, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if body.min_score > body.max_score:
        raise HTTPException(400, "Minimum score cannot exceed the maximum score")
    b = GradingBand(name=body.name.strip(), min_score=body.min_score, max_score=body.max_score,
                    grade_point=body.grade_point, remark=body.remark)
    db.add(b); db.commit(); db.refresh(b)
    audit(db, user, "create", "grading_band", b.id, b.name)
    return {"id": b.id, "name": b.name, "min_score": b.min_score, "max_score": b.max_score,
            "grade_point": b.grade_point, "remark": b.remark}


@router.put("/admin/grading-bands/{band_id}")
def update_band(band_id: int, body: BandBody, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    b = db.query(GradingBand).filter(GradingBand.id == band_id).first()
    if not b:
        raise HTTPException(404, "Grading band not found")
    if body.min_score > body.max_score:
        raise HTTPException(400, "Minimum score cannot exceed the maximum score")
    b.name = body.name.strip(); b.min_score = body.min_score; b.max_score = body.max_score
    b.grade_point = body.grade_point; b.remark = body.remark
    db.commit(); db.refresh(b)
    audit(db, user, "update", "grading_band", b.id, b.name)
    return {"id": b.id, "name": b.name, "min_score": b.min_score, "max_score": b.max_score,
            "grade_point": b.grade_point, "remark": b.remark}


@router.delete("/admin/grading-bands/{band_id}")
def delete_band(band_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    b = db.query(GradingBand).filter(GradingBand.id == band_id).first()
    if not b:
        raise HTTPException(404, "Grading band not found")
    db.delete(b); db.commit()
    audit(db, user, "delete", "grading_band", band_id, b.name)
    return {"message": "Grading band deleted"}


# ── Assessments ──────────────────────────────────────────────────────────────
class AssessmentBody(BaseModel):
    course_id: int
    batch_id: Optional[int] = None
    title: str = Field(min_length=2, max_length=160)
    component: str = "continuous"
    max_score: float = Field(default=100, gt=0, le=1000)
    weight: Optional[float] = Field(default=None, ge=0, le=100)


@router.get("/assessments")
def list_assessments(user: User = Depends(require_roles("faculty", "admin")), db: Session = Depends(get_db),
                     course_id: Optional[int] = None, batch_id: Optional[int] = None):
    q = db.query(Assessment)
    if user.role == "faculty":
        mine = [c.id for c in db.query(Course).filter(Course.lecturer_id == user.id).all()]
        q = q.filter(Assessment.course_id.in_(mine or [-1]))
    if course_id:
        q = q.filter(Assessment.course_id == course_id)
    if batch_id:
        q = q.filter(Assessment.batch_id == batch_id)
    rows = q.order_by(Assessment.created_at.desc()).all()
    return [_assessment_dict(a, db, with_counts=True) for a in rows]


@router.post("/assessments", status_code=201)
def create_assessment(body: AssessmentBody, user: User = Depends(require_roles("faculty", "admin")),
                      db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == body.course_id).first()
    if not course:
        raise HTTPException(404, "Course not found")
    if user.role == "faculty" and course.lecturer_id != user.id:
        raise HTTPException(403, "You can only assess your own courses")
    if body.batch_id is not None:
        batch = db.query(CourseBatch).filter(CourseBatch.id == body.batch_id).first()
        if not batch or batch.course_id != course.id:
            raise HTTPException(400, "The selected batch does not belong to this course")
    component = (body.component or "continuous").strip()
    if component not in COMPONENTS:
        raise HTTPException(400, f"Component must be one of {', '.join(COMPONENTS)}")
    session = db.query(AcademicSession).filter(AcademicSession.is_current == True).first()
    a = Assessment(course_id=course.id, batch_id=body.batch_id, title=body.title.strip(),
                   component=component, max_score=body.max_score, weight=body.weight,
                   academic_session_id=session.id if session else None, created_by=user.id)
    db.add(a); db.commit(); db.refresh(a)
    audit(db, user, "create", "assessment", a.id, f"{course.code}: {a.title}")
    publish_sync("assessments", {"action": "create", "course_id": course.id}, roles=["admin"])
    return _assessment_dict(a, db)


@router.put("/assessments/{assessment_id}")
def update_assessment(assessment_id: int, body: AssessmentBody,
                      user: User = Depends(require_roles("faculty", "admin")),
                      db: Session = Depends(get_db)):
    a = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not a:
        raise HTTPException(404, "Assessment not found")
    course = db.query(Course).filter(Course.id == a.course_id).first()
    if user.role == "faculty" and course.lecturer_id != user.id:
        raise HTTPException(403, "Not your course")
    if body.course_id != a.course_id:
        # Moving an assessment between courses would orphan existing marks.
        if db.query(Result).filter(Result.assessment_id == assessment_id).count():
            raise HTTPException(409, "This assessment already has marks and cannot be moved to another course")
        target = db.query(Course).filter(Course.id == body.course_id).first()
        if not target:
            raise HTTPException(404, "Course not found")
        if user.role == "faculty" and target.lecturer_id != user.id:
            raise HTTPException(403, "You can only assess your own courses")
        a.course_id = target.id
    if body.batch_id is not None:
        batch = db.query(CourseBatch).filter(CourseBatch.id == body.batch_id).first()
        if not batch or batch.course_id != a.course_id:
            raise HTTPException(400, "The selected batch does not belong to this course")
    component = (body.component or "continuous").strip()
    if component not in COMPONENTS:
        raise HTTPException(400, f"Component must be one of {', '.join(COMPONENTS)}")
    a.batch_id = body.batch_id
    a.title = body.title.strip()
    a.component = component
    a.max_score = body.max_score
    a.weight = body.weight
    db.commit(); db.refresh(a)
    audit(db, user, "update", "assessment", a.id, a.title)
    publish_sync("assessments", {"action": "update", "course_id": a.course_id}, roles=["admin"])
    return _assessment_dict(a, db)


@router.delete("/assessments/{assessment_id}")
def delete_assessment(assessment_id: int, user: User = Depends(require_roles("faculty", "admin")),
                      db: Session = Depends(get_db)):
    a = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not a:
        raise HTTPException(404, "Assessment not found")
    course = db.query(Course).filter(Course.id == a.course_id).first()
    if user.role == "faculty" and course and course.lecturer_id != user.id:
        raise HTTPException(403, "Not your course")
    db.query(Result).filter(Result.assessment_id == assessment_id).delete()
    db.delete(a); db.commit()
    audit(db, user, "delete", "assessment", assessment_id, a.title)
    return {"message": "Assessment deleted"}


class MarksBody(BaseModel):
    marks: list[dict]          # [{student_id, score}]
    reason: Optional[str] = None


@router.post("/assessments/{assessment_id}/marks")
def enter_marks(assessment_id: int, body: MarksBody,
                user: User = Depends(require_roles("faculty", "admin")), db: Session = Depends(get_db)):
    a = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not a:
        raise HTTPException(404, "Assessment not found")
    course = db.query(Course).filter(Course.id == a.course_id).first()
    if user.role == "faculty" and course.lecturer_id != user.id:
        raise HTTPException(403, "Not your course")

    # Only enrolled students may receive a mark.
    enrolled = {e.student_id for e in db.query(CourseEnrolment).filter(
        CourseEnrolment.course_id == a.course_id, CourseEnrolment.status == "approved").all()}
    if a.batch_id:
        enrolled = {e.student_id for e in db.query(CourseEnrolment).filter(
            CourseEnrolment.course_id == a.course_id, CourseEnrolment.batch_id == a.batch_id,
            CourseEnrolment.status == "approved").all()}

    updated = 0
    for item in body.marks:
        try:
            sid = int(item["student_id"])
            score = item.get("score")
            score = None if score in (None, "") else float(score)
        except (KeyError, TypeError, ValueError):
            raise HTTPException(400, "Each mark needs a student_id and a numeric score")
        if sid not in enrolled:
            raise HTTPException(400, f"Student {sid} is not enrolled in this course")
        if score is not None and (score < 0 or score > a.max_score):
            raise HTTPException(400, f"Score for student {sid} must be between 0 and {a.max_score}")
        grade, remark = _grade_for(db, score, a.max_score)
        row = db.query(Result).filter(Result.assessment_id == assessment_id,
                                      Result.student_id == sid).first()
        if row:
            if row.score != score:
                db.add(ResultAudit(result_id=row.id, previous_score=row.score, new_score=score,
                                   reason=body.reason, actor_id=user.id, actor_name=user.name))
            row.score = score; row.grade = grade; row.remark = remark; row.entered_by = user.id
        else:
            db.add(Result(assessment_id=assessment_id, student_id=sid, course_id=a.course_id,
                          score=score, grade=grade, remark=remark, entered_by=user.id))
        updated += 1
    db.commit()
    audit(db, user, "enter_marks", "assessment", assessment_id, f"{updated} marks")
    return {"message": f"{updated} mark(s) saved", "updated": updated}


@router.post("/assessments/{assessment_id}/release")
def release_assessment(assessment_id: int, user: User = Depends(require_roles("faculty", "admin")),
                       db: Session = Depends(get_db), release: bool = True):
    a = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not a:
        raise HTTPException(404, "Assessment not found")
    course = db.query(Course).filter(Course.id == a.course_id).first()
    if user.role == "faculty" and course.lecturer_id != user.id:
        raise HTTPException(403, "Not your course")
    a.is_released = release
    db.query(Result).filter(Result.assessment_id == assessment_id).update({"is_released": release})
    db.commit()
    if release:
        q = db.query(CourseEnrolment).filter(CourseEnrolment.course_id == a.course_id,
                                             CourseEnrolment.status == "approved")
        if a.batch_id:
            q = q.filter(CourseEnrolment.batch_id == a.batch_id)
        student_ids = [e.student_id for e in q.all()]
        notify_many(db, student_ids, "New result released",
                    f"Results for {course.code} — {a.title} are now available.",
                    category="result", link="/student/results")
    audit(db, user, "release_results" if release else "unrelease_results", "assessment", a.id, a.title)
    publish_sync("results", {"action": "release" if release else "unrelease", "assessment_id": a.id},
                 roles=["admin", "student"])
    return {"message": f"Results {'released' if release else 'withdrawn'}", "is_released": release}


@router.get("/assessments/{assessment_id}/results")
def assessment_results(assessment_id: int, user: User = Depends(require_roles("faculty", "admin")),
                       db: Session = Depends(get_db)):
    a = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not a:
        raise HTTPException(404, "Assessment not found")
    course = db.query(Course).filter(Course.id == a.course_id).first()
    if user.role == "faculty" and course.lecturer_id != user.id:
        raise HTTPException(403, "Not your course")
    rows = db.query(Result, User).join(User, Result.student_id == User.id).filter(
        Result.assessment_id == assessment_id).all()
    out = [{"student_id": s.id, "student_name": s.name, "index_number": s.index_number,
            "score": r.score, "grade": r.grade, "remark": r.remark} for r, s in rows]
    out.sort(key=lambda r: natural_key(r["index_number"]))
    return {"assessment": _assessment_dict(a, db), "results": out}


# ── Student: my results ──────────────────────────────────────────────────────
@router.get("/student/results")
def my_results(user: User = Depends(require_roles("student")), db: Session = Depends(get_db)):
    approved = [e.course_id for e in db.query(CourseEnrolment).filter(
        CourseEnrolment.student_id == user.id, CourseEnrolment.status == "approved").all()]
    if not approved:
        return []
    rows = db.query(Result, Assessment).join(Assessment, Result.assessment_id == Assessment.id).filter(
        Result.student_id == user.id, Result.course_id.in_(approved),
        Result.is_released == True).all()
    out = []
    for r, a in rows:
        course = db.query(Course).filter(Course.id == r.course_id).first()
        out.append({"course_id": r.course_id, "course_code": course.code if course else None,
                    "course_title": course.title if course else None,
                    "assessment": a.title, "component": a.component, "max_score": a.max_score,
                    "score": r.score, "grade": r.grade, "remark": r.remark})
    return out


# ── Announcements ────────────────────────────────────────────────────────────
class AnnouncementBody(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    body: Optional[str] = None
    audience: str = "all"          # all | lecturers | students | programme | course | batch
    programme_id: Optional[int] = None
    course_id: Optional[int] = None
    batch_id: Optional[int] = None


def _audience_user_ids(db: Session, ann: Announcement):
    if ann.audience == "lecturers":
        return [u.id for u in db.query(User).filter(User.role == "faculty").all()]
    if ann.audience == "students":
        return [u.id for u in db.query(User).filter(User.role == "student",
                                                    User.is_approved == True).all()]
    if ann.audience == "programme" and ann.programme_id:
        return [u.id for u in db.query(User).filter(User.programme_id == ann.programme_id,
                                                    User.is_approved == True).all()]
    if ann.audience == "course" and ann.course_id:
        return [e.student_id for e in db.query(CourseEnrolment).filter(
            CourseEnrolment.course_id == ann.course_id, CourseEnrolment.status == "approved").all()]
    if ann.audience == "batch" and ann.batch_id:
        return [e.student_id for e in db.query(CourseEnrolment).filter(
            CourseEnrolment.batch_id == ann.batch_id, CourseEnrolment.status == "approved").all()]
    return [u.id for u in db.query(User).filter(User.is_approved == True).all()]


@router.post("/announcements", status_code=201)
def create_announcement(body: AnnouncementBody,
                        user: User = Depends(require_roles("admin", "faculty")),
                        db: Session = Depends(get_db)):
    if body.audience not in ("all", "lecturers", "students", "programme", "course", "batch"):
        raise HTTPException(400, "Unsupported audience")
    if body.audience in ("course", "batch"):
        if not body.course_id:
            raise HTTPException(400, "Select a course for this audience")
        course = db.query(Course).filter(Course.id == body.course_id).first()
        if not course:
            raise HTTPException(404, "Course not found")
        if user.role == "faculty" and course.lecturer_id != user.id:
            raise HTTPException(403, "You can only announce to your own courses")
    ann = Announcement(title=body.title.strip(), body=(body.body or "").strip() or None,
                       audience=body.audience, programme_id=body.programme_id,
                       course_id=body.course_id, batch_id=body.batch_id, created_by=user.id)
    db.add(ann); db.commit(); db.refresh(ann)
    ids = _audience_user_ids(db, ann)
    notify_many(db, ids, ann.title, ann.body or "", category="announcement")
    audit(db, user, "create", "announcement", ann.id, ann.title)
    publish_sync("announcements", {"action": "create", "id": ann.id}, user_ids=ids)
    return {"id": ann.id, "title": ann.title, "audience": ann.audience,
            "recipients": len(set(ids))}


@router.get("/announcements")
def list_announcements(user: User = Depends(require_roles("admin", "faculty")), db: Session = Depends(get_db)):
    q = db.query(Announcement)
    if user.role == "faculty":
        mine = [c.id for c in db.query(Course).filter(Course.lecturer_id == user.id).all()]
        q = q.filter((Announcement.created_by == user.id) | (Announcement.course_id.in_(mine or [-1])))
    rows = q.order_by(Announcement.created_at.desc()).limit(100).all()
    return [{"id": a.id, "title": a.title, "body": a.body, "audience": a.audience,
             "course_id": a.course_id, "batch_id": a.batch_id, "created_by": a.created_by,
             "created_at": a.created_at.isoformat() if a.created_at else None} for a in rows]


def _announcement_visible_to(db: Session, ann: Announcement, user: User) -> bool:
    """Whether a student is a member of the audience an announcement targets."""
    if ann.audience == "all":
        return True
    if ann.audience == "students":
        return True
    if ann.audience == "programme":
        return bool(ann.programme_id) and ann.programme_id == user.programme_id
    if ann.audience == "course":
        return bool(ann.course_id) and db.query(CourseEnrolment).filter(
            CourseEnrolment.course_id == ann.course_id,
            CourseEnrolment.student_id == user.id,
            CourseEnrolment.status == "approved").first() is not None
    if ann.audience == "batch":
        return bool(ann.batch_id) and db.query(CourseEnrolment).filter(
            CourseEnrolment.batch_id == ann.batch_id,
            CourseEnrolment.student_id == user.id,
            CourseEnrolment.status == "approved").first() is not None
    # Lecturers/faculty-only audiences are not shown to students.
    return False


@router.get("/student/announcements")
def list_student_announcements(user: User = Depends(require_roles("student")),
                               db: Session = Depends(get_db)):
    rows = db.query(Announcement).order_by(Announcement.created_at.desc()).limit(200).all()
    out = []
    for a in rows:
        if not _announcement_visible_to(db, a, user):
            continue
        author = db.query(User).filter(User.id == a.created_by).first()
        course = db.query(Course).filter(Course.id == a.course_id).first() if a.course_id else None
        out.append({"id": a.id, "title": a.title, "body": a.body, "audience": a.audience,
                    "course_id": a.course_id, "course_code": course.code if course else None,
                    "author": author.name if author else "Smart Campus",
                    "created_at": a.created_at.isoformat() if a.created_at else None})
    return out


@router.put("/announcements/{announcement_id}")
def update_announcement(announcement_id: int, body: AnnouncementBody,
                        user: User = Depends(require_roles("admin", "faculty")),
                        db: Session = Depends(get_db)):
    ann = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not ann:
        raise HTTPException(404, "Announcement not found")
    if user.role == "faculty" and ann.created_by != user.id:
        raise HTTPException(403, "You can only edit your own announcements")
    if body.audience not in ("all", "lecturers", "students", "programme", "course", "batch"):
        raise HTTPException(400, "Unsupported audience")
    if body.audience in ("course", "batch"):
        if not body.course_id:
            raise HTTPException(400, "Select a course for this audience")
        course = db.query(Course).filter(Course.id == body.course_id).first()
        if not course:
            raise HTTPException(404, "Course not found")
        if user.role == "faculty" and course.lecturer_id != user.id:
            raise HTTPException(403, "You can only announce to your own courses")
    ann.title = body.title.strip()
    ann.body = (body.body or "").strip() or None
    ann.audience = body.audience
    ann.programme_id = body.programme_id
    ann.course_id = body.course_id
    ann.batch_id = body.batch_id
    db.commit(); db.refresh(ann)
    audit(db, user, "update", "announcement", ann.id, ann.title)
    publish_sync("announcements", {"action": "update", "id": ann.id}, roles=["admin"])
    return {"id": ann.id, "title": ann.title, "audience": ann.audience}


@router.delete("/announcements/{announcement_id}")
def delete_announcement(announcement_id: int,
                        user: User = Depends(require_roles("admin", "faculty")),
                        db: Session = Depends(get_db)):
    ann = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not ann:
        raise HTTPException(404, "Announcement not found")
    if user.role == "faculty" and ann.created_by != user.id:
        raise HTTPException(403, "You can only delete your own announcements")
    db.delete(ann); db.commit()
    audit(db, user, "delete", "announcement", announcement_id, ann.title)
    publish_sync("announcements", {"action": "delete", "id": announcement_id}, roles=["admin"])
    return {"message": "Announcement deleted"}
