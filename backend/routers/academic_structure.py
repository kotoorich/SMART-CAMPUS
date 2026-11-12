"""Institution-scoped academic directory.

Lecturers create and maintain faculties, departments and programmes for their
own institution. Administrators have cross-institution read-only oversight.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from auth import get_current_user
from database import get_db
from models import Faculty, Department, Programme, User, Course, CourseProgramme
from realtime import audit, publish_sync

router = APIRouter(tags=["academic directory"])


class FacultyBody(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    code: str | None = Field(default=None, max_length=40)
    dean: str | None = Field(default=None, max_length=120)


class DepartmentBody(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    code: str | None = Field(default=None, max_length=40)
    faculty_id: int
    head: str | None = Field(default=None, max_length=120)


class ProgrammeBody(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    code: str | None = Field(default=None, max_length=40)
    department_id: int
    award: str | None = Field(default=None, max_length=40)
    duration_years: int | None = Field(default=4, ge=1, le=12)


def _institution(user: User) -> str:
    value = (user.institution_name or "").strip()
    if not value:
        raise HTTPException(400, "Your account has no institution name. Contact the administrator.")
    return value


def _same_institution(value: str | None, institution: str) -> bool:
    return (value or "").strip().casefold() == institution.strip().casefold()


def _directory(db: Session, institution_name: str | None = None):
    query_f = db.query(Faculty)
    query_d = db.query(Department)
    query_p = db.query(Programme)
    if institution_name:
        query_f = query_f.filter(func.lower(Faculty.institution_name) == institution_name.strip().lower())
        query_d = query_d.filter(func.lower(Department.institution_name) == institution_name.strip().lower())
        query_p = query_p.filter(func.lower(Programme.institution_name) == institution_name.strip().lower())
    faculties = query_f.order_by(Faculty.name).all()
    departments = query_d.order_by(Department.name).all()
    programmes = query_p.order_by(Programme.name).all()
    return {
        "faculties": [{"id": x.id, "name": x.name, "code": x.code, "dean": x.dean, "institution_name": x.institution_name} for x in faculties],
        "departments": [{"id": x.id, "name": x.name, "code": x.code, "faculty_id": x.faculty_id, "head": x.head, "institution_name": x.institution_name} for x in departments],
        "programmes": [{"id": x.id, "name": x.name, "code": x.code, "department_id": x.department_id, "award": x.award, "duration_years": x.duration_years, "institution_name": x.institution_name} for x in programmes],
    }


@router.get("/public/institutions")
def public_institutions(db: Session = Depends(get_db)):
    names = {x[0].strip() for x in db.query(User.institution_name).filter(User.institution_name.isnot(None)).distinct().all() if x[0] and x[0].strip()}
    names.update(x[0].strip() for x in db.query(Faculty.institution_name).distinct().all() if x[0] and x[0].strip())
    return {"institutions": sorted(names, key=str.casefold)}


@router.get("/public/academic-directory")
def public_academic_directory(institution_name: str | None = None, db: Session = Depends(get_db)):
    if not institution_name or not institution_name.strip():
        return _directory(db)
    return _directory(db, institution_name.strip())


@router.get("/admin/academic-directory")
def admin_academic_directory(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(403, "Administrator access required")
    return _directory(db)


@router.get("/academic/academic-directory")
def lecturer_academic_directory(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "faculty":
        raise HTTPException(403, "Lecturer access required")
    return _directory(db, _institution(user))


def _lecturer(user: User):
    if user.role != "faculty":
        raise HTTPException(403, "Only lecturers can manage their institution's academic structure")
    return _institution(user)


def _faculty_in_tenant(db: Session, faculty_id: int, institution: str):
    row = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not row or not _same_institution(row.institution_name, institution):
        raise HTTPException(404, "Faculty / school not found in your institution")
    return row


def _department_in_tenant(db: Session, department_id: int, institution: str):
    row = db.query(Department).filter(Department.id == department_id).first()
    if not row or not _same_institution(row.institution_name, institution):
        raise HTTPException(404, "Department not found in your institution")
    return row


def _save(db: Session, user: User, row, action: str, resource: str, detail: str):
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "A matching academic record already exists. Check the name and code.") from exc
    audit(db, user, action, resource, row.id, detail)
    publish_sync("academic_directory", {"action": resource + "_" + action, "id": row.id}, roles=["admin", "faculty"])
    return row


@router.post("/academic/faculties", status_code=201)
def create_faculty(body: FacultyBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    institution = _lecturer(user)
    name = body.name.strip()
    code = (body.code or "").strip().upper() or None
    if db.query(Faculty).filter(func.lower(Faculty.institution_name) == institution.strip().lower(), Faculty.name.ilike(name)).first():
        raise HTTPException(409, "This faculty already exists in your institution")
    row = Faculty(name=name, code=code, dean=(body.dean or "").strip() or None, institution_name=institution)
    row = _save(db, user, row, "create", "faculty_directory", name)
    return {"id": row.id, "name": row.name, "code": row.code, "dean": row.dean, "institution_name": row.institution_name}


@router.put("/academic/faculties/{faculty_id}")
def update_faculty(faculty_id: int, body: FacultyBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    institution = _lecturer(user)
    row = _faculty_in_tenant(db, faculty_id, institution)
    row.name = body.name.strip(); row.code = (body.code or "").strip().upper() or None; row.dean = (body.dean or "").strip() or None
    try:
        db.commit(); db.refresh(row)
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(409, "A faculty with that name or code already exists") from exc
    audit(db, user, "update", "faculty_directory", row.id, row.name)
    return {"id": row.id, "name": row.name, "code": row.code, "dean": row.dean, "institution_name": row.institution_name}


@router.delete("/academic/faculties/{faculty_id}")
def delete_faculty(faculty_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    institution = _lecturer(user)
    row = _faculty_in_tenant(db, faculty_id, institution)
    if db.query(Department).filter(Department.faculty_id == faculty_id).first():
        raise HTTPException(409, "Move or delete its departments before deleting this faculty")
    db.delete(row); db.commit(); audit(db, user, "delete", "faculty_directory", faculty_id)
    return {"message": "Faculty deleted"}


@router.post("/academic/departments", status_code=201)
def create_department(body: DepartmentBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    institution = _lecturer(user)
    _faculty_in_tenant(db, body.faculty_id, institution)
    name = body.name.strip(); code = (body.code or "").strip().upper() or None
    if db.query(Department).filter(func.lower(Department.institution_name) == institution.strip().lower(), Department.faculty_id == body.faculty_id, Department.name.ilike(name)).first():
        raise HTTPException(409, "This department already exists under that faculty")
    row = Department(name=name, code=code, faculty_id=body.faculty_id, head=(body.head or "").strip() or None, institution_name=institution)
    row = _save(db, user, row, "create", "department_directory", name)
    return {"id": row.id, "name": row.name, "code": row.code, "faculty_id": row.faculty_id, "head": row.head, "institution_name": row.institution_name}


@router.put("/academic/departments/{department_id}")
def update_department(department_id: int, body: DepartmentBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    institution = _lecturer(user)
    row = _department_in_tenant(db, department_id, institution)
    _faculty_in_tenant(db, body.faculty_id, institution)
    row.name = body.name.strip(); row.code = (body.code or "").strip().upper() or None; row.faculty_id = body.faculty_id; row.head = (body.head or "").strip() or None
    try:
        db.commit(); db.refresh(row)
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(409, "A department with that name or code already exists") from exc
    audit(db, user, "update", "department_directory", row.id, row.name)
    return {"id": row.id, "name": row.name, "code": row.code, "faculty_id": row.faculty_id, "head": row.head, "institution_name": row.institution_name}


@router.delete("/academic/departments/{department_id}")
def delete_department(department_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    institution = _lecturer(user)
    row = _department_in_tenant(db, department_id, institution)
    if db.query(Programme).filter(Programme.department_id == department_id).first() or db.query(User).filter(User.department_id == department_id).first() or db.query(Course).filter(Course.department_id == department_id).first():
        raise HTTPException(409, "This department is assigned to programmes, users or courses and cannot be deleted")
    db.delete(row); db.commit(); audit(db, user, "delete", "department_directory", department_id)
    return {"message": "Department deleted"}


@router.post("/academic/programmes", status_code=201)
def create_programme(body: ProgrammeBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    institution = _lecturer(user)
    department = _department_in_tenant(db, body.department_id, institution)
    code = (body.code or "").strip().upper() or None
    if db.query(Programme).filter(func.lower(Programme.institution_name) == institution.strip().lower(), Programme.department_id == department.id, Programme.name.ilike(body.name.strip())).first():
        raise HTTPException(409, "This programme already exists in the department")
    row = Programme(name=body.name.strip(), code=code, department_id=department.id, award=(body.award or "").strip() or None, duration_years=body.duration_years, institution_name=institution)
    row = _save(db, user, row, "create", "programme_directory", row.name)
    return {"id": row.id, "name": row.name, "code": row.code, "department_id": row.department_id, "award": row.award, "duration_years": row.duration_years, "institution_name": row.institution_name}


@router.put("/academic/programmes/{programme_id}")
def update_programme(programme_id: int, body: ProgrammeBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    institution = _lecturer(user)
    row = db.query(Programme).filter(Programme.id == programme_id, Programme.institution_name.ilike(institution)).first()
    if not row: raise HTTPException(404, "Programme not found in your institution")
    _department_in_tenant(db, body.department_id, institution)
    row.name = body.name.strip(); row.code = (body.code or "").strip().upper() or None; row.department_id = body.department_id; row.award = (body.award or "").strip() or None; row.duration_years = body.duration_years
    try:
        db.commit(); db.refresh(row)
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(409, "A programme with that name or code already exists") from exc
    audit(db, user, "update", "programme_directory", row.id, row.name)
    return {"id": row.id, "name": row.name, "code": row.code, "department_id": row.department_id, "award": row.award, "duration_years": row.duration_years, "institution_name": row.institution_name}


@router.delete("/academic/programmes/{programme_id}")
def delete_programme(programme_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    institution = _lecturer(user)
    row = db.query(Programme).filter(Programme.id == programme_id, Programme.institution_name.ilike(institution)).first()
    if not row: raise HTTPException(404, "Programme not found in your institution")
    if db.query(Course).filter(Course.programme_id == programme_id).first() or db.query(CourseProgramme).filter(CourseProgramme.programme_id == programme_id).first() or db.query(User).filter(User.programme_id == programme_id).first():
        raise HTTPException(409, "This programme is in use by courses or students and cannot be deleted")
    db.delete(row); db.commit(); audit(db, user, "delete", "programme_directory", programme_id)
    return {"message": "Programme deleted"}


# Administrator supervisory deletion. Administrators may remove directory records
# across institutions, but cannot create or edit them. Deletion is deliberately
# restricted to unreferenced records so existing students/courses are never orphaned.
def _admin_directory_user(user: User):
    if user.role != "admin":
        raise HTTPException(403, "Administrator access required")
    return user


@router.delete("/admin/academic/faculties/{faculty_id}")
def admin_delete_faculty(faculty_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _admin_directory_user(user)
    row = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not row:
        raise HTTPException(404, "Faculty / school not found")
    if db.query(Department).filter(Department.faculty_id == faculty_id).first():
        raise HTTPException(409, "This faculty still contains departments. Delete or move its departments first.")
    db.delete(row)
    db.commit()
    audit(db, user, "delete", "faculty_directory", faculty_id, f"{row.name} · {row.institution_name}")
    publish_sync("academic_directory", {"action": "faculty_directory_delete", "id": faculty_id}, roles=["admin", "faculty"])
    return {"message": "Faculty deleted"}


@router.delete("/admin/academic/departments/{department_id}")
def admin_delete_department(department_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _admin_directory_user(user)
    row = db.query(Department).filter(Department.id == department_id).first()
    if not row:
        raise HTTPException(404, "Department not found")
    in_use = (
        db.query(Programme).filter(Programme.department_id == department_id).first()
        or db.query(User).filter(User.department_id == department_id).first()
        or db.query(Course).filter(Course.department_id == department_id).first()
    )
    if in_use:
        raise HTTPException(409, "This department is linked to programmes, users or courses. Resolve those records before deleting it.")
    detail = f"{row.name} · {row.institution_name}"
    db.delete(row)
    db.commit()
    audit(db, user, "delete", "department_directory", department_id, detail)
    publish_sync("academic_directory", {"action": "department_directory_delete", "id": department_id}, roles=["admin", "faculty"])
    return {"message": "Department deleted"}


@router.delete("/admin/academic/programmes/{programme_id}")
def admin_delete_programme(programme_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _admin_directory_user(user)
    row = db.query(Programme).filter(Programme.id == programme_id).first()
    if not row:
        raise HTTPException(404, "Programme not found")
    in_use = (
        db.query(Course).filter(Course.programme_id == programme_id).first()
        or db.query(CourseProgramme).filter(CourseProgramme.programme_id == programme_id).first()
        or db.query(User).filter(User.programme_id == programme_id).first()
    )
    if in_use:
        raise HTTPException(409, "This programme is linked to courses or students. Resolve those records before deleting it.")
    detail = f"{row.name} · {row.institution_name}"
    db.delete(row)
    db.commit()
    audit(db, user, "delete", "programme_directory", programme_id, detail)
    publish_sync("academic_directory", {"action": "programme_directory_delete", "id": programme_id}, roles=["admin", "faculty"])
    return {"message": "Programme deleted"}
