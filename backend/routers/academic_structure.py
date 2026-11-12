"""Academic directory APIs.

Institution administrators maintain faculties and departments. Lecturers can
create programmes within their assigned department; administrators retain
oversight and can maintain the directory. The public read endpoint only
returns active directory information needed by registration forms.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Faculty, Department, Programme, User
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


def _admin(user: User):
    if user.role != "admin":
        raise HTTPException(403, "Administrator access required")


def _directory(db: Session):
    faculties = db.query(Faculty).order_by(Faculty.name).all()
    departments = db.query(Department).order_by(Department.name).all()
    programmes = db.query(Programme).order_by(Programme.name).all()
    return {
        "faculties": [{"id": x.id, "name": x.name, "code": x.code, "dean": x.dean} for x in faculties],
        "departments": [{"id": x.id, "name": x.name, "code": x.code, "faculty_id": x.faculty_id, "head": x.head} for x in departments],
        "programmes": [{"id": x.id, "name": x.name, "code": x.code, "department_id": x.department_id, "award": x.award, "duration_years": x.duration_years} for x in programmes],
    }


@router.get("/public/academic-directory")
def public_academic_directory(db: Session = Depends(get_db)):
    return _directory(db)


@router.get("/admin/academic-directory")
def admin_academic_directory(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _admin(user)
    return _directory(db)


@router.post("/admin/faculties", status_code=201)
def create_faculty(body: FacultyBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _admin(user)
    name = body.name.strip()
    if db.query(Faculty).filter(Faculty.name.ilike(name)).first():
        raise HTTPException(409, "Faculty already exists")
    row = Faculty(name=name, code=(body.code or "").strip().upper() or None, dean=(body.dean or "").strip() or None)
    db.add(row); db.commit(); db.refresh(row)
    audit(db, user, "create", "faculty_directory", row.id, row.name)
    publish_sync("academic_directory", {"action": "faculty_created", "id": row.id}, roles=["admin", "faculty"])
    return {"id": row.id, "name": row.name, "code": row.code, "dean": row.dean}


@router.put("/admin/faculties/{faculty_id}")
def update_faculty(faculty_id: int, body: FacultyBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _admin(user)
    row = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not row: raise HTTPException(404, "Faculty not found")
    if db.query(Faculty).filter(Faculty.name.ilike(body.name.strip()), Faculty.id != faculty_id).first():
        raise HTTPException(409, "Faculty already exists")
    row.name = body.name.strip(); row.code = (body.code or "").strip().upper() or None; row.dean = (body.dean or "").strip() or None
    db.commit(); db.refresh(row)
    audit(db, user, "update", "faculty_directory", row.id, row.name)
    return {"id": row.id, "name": row.name, "code": row.code, "dean": row.dean}


@router.delete("/admin/faculties/{faculty_id}")
def delete_faculty(faculty_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _admin(user)
    row = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not row: raise HTTPException(404, "Faculty not found")
    if db.query(Department).filter(Department.faculty_id == faculty_id).first():
        raise HTTPException(409, "Move or delete its departments before deleting this faculty")
    db.delete(row); db.commit()
    audit(db, user, "delete", "faculty_directory", faculty_id)
    return {"message": "Faculty deleted"}


@router.post("/admin/departments", status_code=201)
def create_department(body: DepartmentBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _admin(user)
    if not db.query(Faculty).filter(Faculty.id == body.faculty_id).first():
        raise HTTPException(404, "Select a valid faculty")
    name = body.name.strip()
    if db.query(Department).filter(Department.faculty_id == body.faculty_id, Department.name.ilike(name)).first():
        raise HTTPException(409, "Department already exists in this faculty")
    row = Department(name=name, code=(body.code or "").strip().upper() or None, faculty_id=body.faculty_id, head=(body.head or "").strip() or None)
    db.add(row); db.commit(); db.refresh(row)
    audit(db, user, "create", "department_directory", row.id, row.name)
    publish_sync("academic_directory", {"action": "department_created", "id": row.id}, roles=["admin", "faculty"])
    return {"id": row.id, "name": row.name, "code": row.code, "faculty_id": row.faculty_id, "head": row.head}


@router.put("/admin/departments/{department_id}")
def update_department(department_id: int, body: DepartmentBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _admin(user)
    row = db.query(Department).filter(Department.id == department_id).first()
    if not row: raise HTTPException(404, "Department not found")
    if not db.query(Faculty).filter(Faculty.id == body.faculty_id).first():
        raise HTTPException(404, "Select a valid faculty")
    if db.query(Department).filter(Department.faculty_id == body.faculty_id, Department.name.ilike(body.name.strip()), Department.id != department_id).first():
        raise HTTPException(409, "Department already exists in this faculty")
    row.name = body.name.strip(); row.code = (body.code or "").strip().upper() or None; row.faculty_id = body.faculty_id; row.head = (body.head or "").strip() or None
    db.commit(); db.refresh(row)
    audit(db, user, "update", "department_directory", row.id, row.name)
    return {"id": row.id, "name": row.name, "code": row.code, "faculty_id": row.faculty_id, "head": row.head}


@router.delete("/admin/departments/{department_id}")
def delete_department(department_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _admin(user)
    row = db.query(Department).filter(Department.id == department_id).first()
    if not row: raise HTTPException(404, "Department not found")
    if db.query(Programme).filter(Programme.department_id == department_id).first():
        raise HTTPException(409, "Move or delete its programmes before deleting this department")
    db.delete(row); db.commit()
    audit(db, user, "delete", "department_directory", department_id)
    return {"message": "Department deleted"}


@router.post("/academic/programmes", status_code=201)
def create_programme(body: ProgrammeBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "faculty":
        raise HTTPException(403, "Only lecturers can create and manage department programmes")
    department = db.query(Department).filter(Department.id == body.department_id).first()
    if not department: raise HTTPException(404, "Department not found")
    if user.role == "faculty" and user.department_id != department.id:
        raise HTTPException(403, "Lecturers can only create programmes within their assigned department")
    if db.query(Programme).filter(Programme.department_id == department.id, Programme.name.ilike(body.name.strip())).first():
        raise HTTPException(409, "Programme already exists in this department")
    row = Programme(name=body.name.strip(), code=(body.code or "").strip().upper() or None, department_id=department.id, award=(body.award or "").strip() or None, duration_years=body.duration_years)
    db.add(row); db.commit(); db.refresh(row)
    audit(db, user, "create", "programme_directory", row.id, row.name)
    publish_sync("academic_directory", {"action": "programme_created", "id": row.id}, roles=["admin", "faculty"])
    return {"id": row.id, "name": row.name, "code": row.code, "department_id": row.department_id, "award": row.award, "duration_years": row.duration_years}


@router.put("/academic/programmes/{programme_id}")
def update_programme(programme_id: int, body: ProgrammeBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in ("admin", "faculty"):
        raise HTTPException(403, "Only lecturers or administrators can manage programmes")
    row = db.query(Programme).filter(Programme.id == programme_id).first()
    if not row: raise HTTPException(404, "Programme not found")
    department = db.query(Department).filter(Department.id == body.department_id).first()
    if not department: raise HTTPException(404, "Department not found")
    if user.role == "faculty" and (user.department_id != row.department_id or user.department_id != department.id):
        raise HTTPException(403, "Lecturers can only manage programmes within their assigned department")
    if db.query(Programme).filter(Programme.department_id == department.id, Programme.name.ilike(body.name.strip()), Programme.id != programme_id).first():
        raise HTTPException(409, "Programme already exists in this department")
    row.name = body.name.strip(); row.code = (body.code or "").strip().upper() or None; row.department_id = department.id; row.award = (body.award or "").strip() or None; row.duration_years = body.duration_years
    db.commit(); db.refresh(row)
    audit(db, user, "update", "programme_directory", row.id, row.name)
    return {"id": row.id, "name": row.name, "code": row.code, "department_id": row.department_id, "award": row.award, "duration_years": row.duration_years}


@router.delete("/academic/programmes/{programme_id}")
def delete_programme(programme_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in ("admin", "faculty"):
        raise HTTPException(403, "Only lecturers or administrators can manage programmes")
    row = db.query(Programme).filter(Programme.id == programme_id).first()
    if not row: raise HTTPException(404, "Programme not found")
    if user.role == "faculty" and user.department_id != row.department_id:
        raise HTTPException(403, "Lecturers can only manage programmes within their assigned department")
    from models import Course, CourseProgramme
    if db.query(Course).filter(Course.programme_id == programme_id).first() or db.query(CourseProgramme).filter(CourseProgramme.programme_id == programme_id).first() or db.query(User).filter(User.programme_id == programme_id).first():
        raise HTTPException(409, "This programme is in use by courses or students and cannot be deleted")
    db.delete(row); db.commit()
    audit(db, user, "delete", "programme_directory", programme_id)
    return {"message": "Programme deleted"}
