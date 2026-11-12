"""Backend integration tests for the independent Smart Campus attendance API.

These tests run against an isolated temporary SQLite database using FastAPI's
TestClient, so they exercise the real routers, models, migrations and seed
routine without touching a development database.

Run with:
    cd backend && .venv/bin/python -m pytest -q
"""
import base64
import io
import os
import tempfile
from datetime import date, datetime

import pytest

# The database must be configured before the application modules import it.
_TMP_DB = tempfile.NamedTemporaryFile(prefix="smart_campus_test_", suffix=".db", delete=False)
_TMP_DB.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.name}"
os.environ["SEED_DEMO_DATA"] = "true"
os.environ["ENVIRONMENT"] = "development"
os.environ["DEV_ALLOW_ANY_TIME"] = "true"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-automated-tests-only"
os.environ["APP_TIMEZONE"] = "Africa/Accra"

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
from database import SessionLocal  # noqa: E402
from models import Course, GradingBand  # noqa: E402

client = TestClient(main.app)

ADMIN = ("admin@smartcampus.com", "Admin@12345", "admin")
FACULTY = ("faculty1@smartcampus.com", "Lecturer@12345", "faculty")
STUDENT = ("student@smartcampus.com", "Student@12345", "student")


def _token(creds):
    email, password, role = creds
    res = client.post("/login", json={"email": email, "password": password, "selected_role": role})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def auth(creds):
    return {"Authorization": f"Bearer {_token(creds)}"}


@pytest.fixture(scope="module")
def admin():
    return auth(ADMIN)


@pytest.fixture(scope="module")
def faculty():
    return auth(FACULTY)


@pytest.fixture(scope="module")
def student():
    return auth(STUDENT)


def _selfie_b64() -> str:
    """A minimal, valid PNG image encoded as a data URL."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (12, 34, 56)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _lecturer_id(admin):
    return client.get("/admin/faculty", headers=admin).json()[0]["id"]


# ── Health & authentication ─────────────────────────────────────────────────
def test_health():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_login_all_three_roles():
    for creds in (ADMIN, FACULTY, STUDENT):
        res = client.post("/login", json={"email": creds[0], "password": creds[1], "selected_role": creds[2]})
        assert res.status_code == 200, res.text
        assert res.json()["role"] == creds[2]
        assert res.json()["access_token"]


def test_login_wrong_password():
    assert client.post("/login", json={"email": ADMIN[0], "password": "wrong",
                                       "selected_role": "admin"}).status_code == 401


def test_login_role_mismatch():
    assert client.post("/login", json={"email": STUDENT[0], "password": STUDENT[1],
                                       "selected_role": "admin"}).status_code == 403


def test_protected_route_requires_token():
    assert client.get("/admin/stats").status_code == 401


def test_role_authorization():
    student = auth(STUDENT)
    faculty = auth(FACULTY)
    assert client.get("/admin/stats", headers=student).status_code == 403
    assert client.get("/admin/stats", headers=faculty).status_code == 403
    assert client.get("/admin/students", headers=student).status_code == 403


# ── Academic structure ──────────────────────────────────────────────────────
def test_seed_has_three_accounts_and_courses(admin):
    users = client.get("/admin/students", headers=admin).json()
    assert len(users) == 1, "seed must create exactly one demo student"
    courses = client.get("/academic/courses", headers=admin).json()
    assert len(courses) == 3, "seed must create exactly three canonical courses"
    assert {c["code"] for c in courses} == {"IT101", "DB201", "SE301"}
    for c in courses:
        assert c["batches"], f"{c['code']} should have at least one batch"
    db = SessionLocal()
    try:
        assert db.query(GradingBand).count() >= 1
    finally:
        db.close()


def test_student_signup_with_institution_profile():
    res = client.post("/student/signup", json={
        "name": "New Applicant", "index_number": "2024999", "email": "applicant@example.com",
        "password": "StrongPass@1", "phone": "+233240000999",
        "ghana_card_number": "GHA-123456789-0", "registration_selfie": _selfie_b64(),
        "consent_biometrics": True, "institution_name": "Example University",
        "faculty_name": "School of Technology", "department_name": "Computing",
        "programme_name": "BSc Computer Science", "programme_id": client.get("/public/academic-directory").json()["programmes"][0]["id"], "academic_year": "2026/2027",
        "level": 100, "interests": "ai",
    })
    assert res.status_code == 200, res.text
    assert res.json()["status"] in ("approved", "pending")
    res = client.post("/student/signup", json={
        "name": "Dup", "index_number": "2024999", "email": "other@example.com",
        "password": "StrongPass@1", "phone": "+233240000998",
        "ghana_card_number": "GHA-987654321-0", "registration_selfie": _selfie_b64(),
        "consent_biometrics": True, "institution_name": "Example University",
        "faculty_name": "School of Technology", "department_name": "Computing",
        "programme_name": "BSc Computer Science", "programme_id": client.get("/public/academic-directory").json()["programmes"][0]["id"], "academic_year": "2026/2027",
    })
    assert res.status_code == 409


# ── Course + batch + timetable integration ──────────────────────────────────
def test_course_timetable_integration(admin, faculty, student):
    lecturer_id = _lecturer_id(admin)
    res = client.post("/academic/courses", headers=faculty, json={
        "title": "Integration Test Course", "code": "ITC101", "lecturer_id": lecturer_id,
        "programme_id": client.get("/public/academic-directory").json()["programmes"][0]["id"],
        "level": "100", "semester": "First Semester", "credit_hours": 3,
        "is_published": True, "registration_open": True, "enrolment_requires_approval": False,
        "batch_names": ["Batch A", "Batch B"],
    })
    assert res.status_code == 201, res.text
    course = res.json()
    course_id = course["id"]
    assert course["registration_code"]
    assert {b["name"] for b in course["batches"]} == {"Batch A", "Batch B"}

    with SessionLocal() as db:
        before = db.query(Course).count()
    res = client.post("/admin/timetable", headers=admin, json={
        "course_id": course_id, "day_of_week": 4, "period": "P4", "section": "AI-1A",
        "class_type": "theory", "is_published": True,
    })
    assert res.status_code == 201, res.text
    slot = res.json()
    assert slot["course_id"] == course_id
    assert slot["course_code"] == "ITC101"
    with SessionLocal() as db:
        assert db.query(Course).count() == before, "timetable entry must not create a course"

    assert client.post("/admin/timetable", headers=admin, json={
        "course_id": course_id, "day_of_week": 4, "period": "P4", "section": "AI-1A",
    }).status_code == 409

    assert client.post("/admin/timetable", headers=admin, json={
        "course_id": course_id, "day_of_week": 5, "period": "P1", "section": "AI-1Z",
        "start_time": "12:00", "end_time": "11:00",
    }).status_code == 400

    assert client.post("/admin/timetable", headers=admin, json={
        "course_id": 999999, "day_of_week": 5, "period": "P1",
    }).status_code == 404


def test_batch_crud_and_validation(admin):
    courses = client.get("/academic/courses", headers=admin).json()
    course = next(c for c in courses if c["code"] == "ITC101")
    res = client.post(f"/admin/courses/{course['id']}/batches", headers=admin,
                      json={"name": "Batch C", "capacity": 2})
    assert res.status_code == 201
    batch_id = res.json()["id"]
    assert res.json()["capacity"] == 2
    assert client.post(f"/admin/courses/{course['id']}/batches", headers=admin,
                       json={"name": "Batch C"}).status_code == 409
    res = client.put(f"/admin/batches/{batch_id}", headers=admin, json={"name": "Batch C2"})
    assert res.status_code == 200
    assert res.json()["name"] == "Batch C2"
    assert client.delete(f"/admin/batches/{batch_id}", headers=admin).status_code == 200


def test_lecturer_sees_assigned_course(admin, faculty):
    data = client.get("/faculty/my-courses", headers=faculty).json()
    itc = next(c for c in data if c["code"] == "ITC101")
    assert itc["batches"], "my-courses should include batch information"


def test_lecturer_can_edit_own_course_details(admin, faculty):
    lecturer_id = _lecturer_id(admin)
    mine = client.post("/academic/courses", headers=faculty, json={
        "title": "Lecturer Editable Course", "code": "LEC101", "lecturer_id": lecturer_id,
        "programme_id": client.get("/public/academic-directory").json()["programmes"][0]["id"],
        "level": "100", "semester": "First Semester", "academic_year": "2025/2026",
        "programme_name": "BSc. Computer Science with Artificial Intelligence & Data Science",
        "batch_names": ["Batch LEC"]}).json()
    res = client.patch(f"/academic/courses/{mine['id']}", headers=faculty,
                       json={"title": "Lecturer Editable Course (Revised)",
                             "description": "Updated description",
                             "credit_hours": 3, "is_published": True})
    assert res.status_code == 200, res.text
    refreshed = next(c for c in client.get("/faculty/my-courses", headers=faculty).json()
                     if c["id"] == mine["id"])
    assert refreshed["title"] == "Lecturer Editable Course (Revised)"
    assert refreshed["is_published"] is True
    # A lecturer must not be able to edit another lecturer's course.
    other_faculty = client.post("/admin/faculty", headers=admin, json={
        "name": "Other Lecturer", "email": "other.lecturer@smartcampus.com",
        "password": "Lecturer@12345", "staff_id": "STF-OTHER", "institution_name": "Smart Campus",
    }).json()
    other_credentials = ("other.lecturer@smartcampus.com", "Lecturer@12345", "faculty")
    other = client.post("/academic/courses", headers=auth(other_credentials), json={
        "title": "Not Mine", "code": "NM101", "lecturer_id": other_faculty["id"],
        "programme_id": client.get("/public/academic-directory").json()["programmes"][0]["id"],
        "level": "100", "semester": "First Semester", "academic_year": "2025/2026",
        "programme_name": "BSc. Information Technology"}).json()
    assert client.patch(f"/academic/courses/{other['id']}", headers=faculty,
                        json={"title": "Hijacked"}).status_code == 403
    assert client.delete(f"/academic/courses/{other['id']}", headers=admin).status_code == 200
    assert client.delete(f"/academic/courses/{mine['id']}", headers=admin).status_code == 200


def test_create_course_with_programme_id_derives_department(admin, faculty):
    """Regression: creating a course by programme_id must not raise NameError.

    The course form offers a programme dropdown that posts programme_id; the
    handler derives the department from the programme's faculty structure.
    """
    lecturer_id = _lecturer_id(admin)
    pid = client.get("/academic/courses", headers=admin).json()[0]["programme_ids"][0]
    res = client.post("/academic/courses", headers=faculty, json={
        "title": "Programme Scoped Course", "code": "PROG501", "lecturer_id": lecturer_id,
        "programme_id": client.get("/public/academic-directory").json()["programmes"][0]["id"],
        "level": "100", "semester": "First Semester", "academic_year": "2025/2026",
        "programme_id": pid, "batch_names": ["Batch PROG"]})
    assert res.status_code == 201, res.text
    created = res.json()
    assert created["programme_id"] == pid
    assert created["department"]
    assert client.delete(f"/academic/courses/{created['id']}", headers=admin).status_code == 200


def test_edit_course_that_has_a_programme_does_not_error(admin):
    """Regression: saving an edit round-trips programme_id back to the API."""
    course = next(c for c in client.get("/academic/courses", headers=admin).json()
                  if c.get("programme_ids"))
    res = client.patch(f"/academic/courses/{course['id']}", headers=admin,
                       json={"title": course["title"], "programme_id": course["programme_ids"][0],
                             "programme_ids": course["programme_ids"]})
    assert res.status_code == 200, res.text


# ── Enrolment (course + batch, auto-approved) ───────────────────────────────
def test_enrol_by_course_and_batch(admin, faculty, student):
    courses = client.get("/academic/courses", headers=admin).json()
    course = next(c for c in courses if c["code"] == "ITC101")
    batch = course["batches"][0]
    res = client.post("/academic/enrol", headers=student,
                      json={"course_id": course["id"], "batch_id": batch["id"], "registration_code": course["registration_code"]})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "approved"
    assert res.json()["batch_id"] == batch["id"]
    student_id = client.get("/profile", headers=student).json()["id"]
    lecturer_id = _lecturer_id(admin)
    assert client.get(f"/profiles/{lecturer_id}", headers=student).status_code == 200
    assert client.get(f"/profiles/{student_id}", headers=faculty).status_code == 200
    assert client.get(f"/profiles/{student_id}", headers=admin).status_code == 200
    assert client.get(f"/profiles/{lecturer_id}", headers=admin).status_code == 200

    assert client.post("/academic/enrol", headers=student,
                       json={"course_id": course["id"], "batch_id": batch["id"], "registration_code": course["registration_code"]}).status_code == 409

    other = next(c for c in courses if c["code"] == "DB201")
    # A course that defines batches requires an explicit batch selection.
    lecturer_id = _lecturer_id(admin)
    res = client.post("/academic/courses", headers=faculty, json={
        "title": "Batch Required Course", "code": "BRC101", "lecturer_id": lecturer_id,
        "programme_id": client.get("/public/academic-directory").json()["programmes"][0]["id"],
        "credit_hours": 1, "is_published": True, "registration_open": True,
        "batch_names": ["Only Batch"],
    })
    assert client.post("/academic/enrol", headers=student,
                       json={"course_id": res.json()["id"], "registration_code": res.json()["registration_code"]}).status_code == 400
    assert other["id"]  # referenced for clarity


def test_student_my_courses_includes_batch(student):
    data = client.get("/student/my-courses", headers=student).json()
    assert data, "student should have enrolled courses"
    itc = next(c for c in data if c["code"] == "ITC101")
    assert itc["batch_name"]


def test_withdraw_and_reregister(admin, student):
    enrolments = client.get("/academic/enrolments", headers=student).json()
    itc = next(e for e in enrolments if e["course_code"] == "ITC101")
    assert client.delete(f"/academic/enrol/{itc['id']}", headers=student).status_code == 200
    withdrawn = client.get("/academic/enrolments", headers=student).json()
    assert next(e for e in withdrawn if e["course_code"] == "ITC101")["status"] == "withdrawn"
    courses = client.get("/academic/courses", headers=admin).json()
    course = next(c for c in courses if c["code"] == "ITC101")
    batch = course["batches"][0]
    res = client.post("/academic/enrol", headers=student,
                      json={"course_id": course["id"], "batch_id": batch["id"], "registration_code": course["registration_code"]})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "approved"


def test_class_list_has_students(admin, faculty, student):
    class_list = client.get("/faculty/class-list", headers=faculty).json()
    itc = next(c for c in class_list if c["course_code"] == "ITC101")
    assert itc["students"], "class list should include the enrolled student"


def test_enrolment_credit_cap(admin, faculty, student):
    original = client.get("/admin/settings", headers=admin).json()
    client.put("/admin/settings", headers=admin, json={**original, "max_credits_per_semester": 3})
    lecturer_id = _lecturer_id(admin)
    res = client.post("/academic/courses", headers=faculty, json={
        "title": "Cap Test Course", "code": "CAP101", "lecturer_id": lecturer_id,
        "programme_id": client.get("/public/academic-directory").json()["programmes"][0]["id"],
        "credit_hours": 3, "is_published": True, "registration_open": True,
    })
    course_id = res.json()["id"]
    assert client.post("/academic/enrol", headers=student,
                       json={"course_id": course_id, "registration_code": res.json()["registration_code"]}).status_code == 403
    client.put("/admin/settings", headers=admin, json={**original, "max_credits_per_semester": 24})


# ── Timetable visibility ────────────────────────────────────────────────────
def test_student_timetable_scoped_to_enrolments(admin, student):
    enrolments = client.get("/academic/enrolments", headers=student).json()
    enrolled_ids = {e["course_id"] for e in enrolments if e["status"] == "approved"}
    slots = client.get("/student/timetable", headers=student).json()
    assert slots, "enrolled student should still see their published timetable"
    for slot in slots:
        if slot["course_id"] is not None:
            assert slot["course_id"] in enrolled_ids, \
                f"timetable leaked course {slot['course_id']} the student is not enrolled in"


def test_timetable_publication_visibility(admin, student):
    client.post("/admin/timetable/publish", headers=admin, json={"publish": False})
    assert client.get("/student/timetable", headers=student).json() == []
    client.post("/admin/timetable/publish", headers=admin, json={"publish": True})
    assert len(client.get("/student/timetable", headers=student).json()) > 0


def test_student_timetable_week_is_day_keyed(student):
    res = client.get("/student/timetable/week", headers=student)
    assert res.status_code == 200
    assert set(res.json()) == {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"}


def test_timetable_update_and_delete(admin, faculty):
    lecturer_id = _lecturer_id(admin)
    res = client.post("/academic/courses", headers=faculty, json={
        "title": "Edit Test Course", "code": "EDT101", "lecturer_id": lecturer_id,
        "programme_id": client.get("/public/academic-directory").json()["programmes"][0]["id"],
        "credit_hours": 2, "is_published": True, "registration_open": True,
    })
    course_id = res.json()["id"]
    res = client.post("/admin/timetable", headers=admin, json={
        "course_id": course_id, "day_of_week": 3, "period": "P3", "section": "EDT-1A",
        "is_published": False,
    })
    assert res.status_code == 201, res.text
    slot_id = res.json()["id"]
    res = client.put(f"/admin/timetable/{slot_id}", headers=admin, json={
        "course_id": course_id, "day_of_week": 3, "period": "P3", "section": "EDT-1A",
        "is_published": True,
    })
    assert res.status_code == 200
    assert res.json()["is_published"] is True
    assert client.delete(f"/admin/timetable/{slot_id}", headers=admin).status_code == 200


# ── Attendance: QR + selfie + GPS ───────────────────────────────────────────
def _make_today_course(admin, faculty, code, period):
    lecturer_id = _lecturer_id(admin)
    weekday = date.today().weekday()
    res = client.post("/academic/courses", headers=faculty, json={
        "title": f"{code} Course", "code": code, "lecturer_id": lecturer_id,
        "programme_id": client.get("/public/academic-directory").json()["programmes"][0]["id"],
        "credit_hours": 1, "is_published": True, "registration_open": True,
        "enrolment_requires_approval": False, "batch_names": ["Batch 1"],
    })
    course = res.json()
    existing = client.get("/admin/timetable", headers=admin).json()
    for s in existing:
        if s["faculty_id"] == lecturer_id and s["day_of_week"] == weekday and s["period"] == period:
            client.delete(f"/admin/timetable/{s['id']}", headers=admin)
    res = client.post("/admin/timetable", headers=admin, json={
        "course_id": course["id"], "day_of_week": weekday, "period": period,
        "section": "AI-1A", "is_published": True,
    })
    assert res.status_code == 201, res.text
    return course



def test_attendance_can_open_without_timetable_and_outside_class_time(admin, faculty):
    lecturer_id = _lecturer_id(admin)
    res = client.post("/academic/courses", headers=faculty, json={
        "title": "Flexible Attendance Course", "code": "FLEX901", "lecturer_id": lecturer_id,
        "programme_id": client.get("/public/academic-directory").json()["programmes"][0]["id"],
        "credit_hours": 1, "is_published": True, "registration_open": True,
    })
    assert res.status_code == 201, res.text
    course = res.json()
    # No timetable row is created. Attendance must still open whenever the
    # lecturer chooses, using the session's own duration and radius.
    opened = client.post("/faculty/attendance/sessions", headers=faculty, json={
        "course_id": course["id"], "latitude": 5.115, "longitude": -1.289,
        "accuracy": 5, "radius_meters": 25, "session_minutes": 45,
    })
    assert opened.status_code == 201, opened.text
    data = opened.json()
    assert data["radius_meters"] == 25
    assert data["is_open"] is True
    assert data["expires_at"]
    assert data["period"].startswith("ADHOC-")

def test_attendance_workflow(admin, faculty, student):
    course = _make_today_course(admin, faculty, "ATT101", "P1")
    batch = course["batches"][0]
    assert client.post("/academic/enrol", headers=student,
                       json={"course_id": course["id"], "batch_id": batch["id"],
                             "registration_code": course["registration_code"]}).status_code == 200

    # Session without GPS is rejected (validated by the model).
    assert client.post("/faculty/attendance/sessions", headers=faculty, json={
        "course_id": course["id"], "period": "P1"}).status_code == 422

    res = client.post("/faculty/attendance/sessions", headers=faculty, json={
        "course_id": course["id"], "period": "P1",
        "latitude": 5.115, "longitude": -1.289, "accuracy": 10})
    assert res.status_code == 201, res.text
    session = res.json()
    token = session["token"]
    assert token

    assert client.post("/student/attendance/mark", headers=student, json={
        "token": "not-a-real-token-xx", "image": _selfie_b64(),
        "latitude": 5.115, "longitude": -1.289, "accuracy": 10}).status_code == 404

    assert client.post("/student/attendance/mark", headers=student, json={
        "token": token, "image": _selfie_b64(),
        "latitude": 6.0, "longitude": -2.0, "accuracy": 10}).status_code == 403

    assert client.post("/student/attendance/mark", headers=student, json={
        "token": token, "image": "x" * 40,
        "latitude": 5.115, "longitude": -1.289, "accuracy": 10}).status_code == 400

    res = client.post("/student/attendance/mark", headers=student, json={
        "token": token, "image": _selfie_b64(),
        "latitude": 5.115, "longitude": -1.289, "accuracy": 10})
    assert res.status_code == 200, res.text
    attendance_id = res.json()["attendance_id"]
    assert "selfie" in res.json()["method"].lower()

    assert client.post("/student/attendance/mark", headers=student, json={
        "token": token, "image": _selfie_b64(),
        "latitude": 5.115, "longitude": -1.289, "accuracy": 10}).status_code == 409

    roster = client.get(f"/faculty/attendance/sessions/{session['id']}", headers=faculty).json()
    assert len(roster["present"]) == 1
    # The session detail must carry its course code and date so the lecturer
    # register heading and CSV export are labelled correctly.
    assert roster["course_code"] == "ATT101" and roster["date"] and roster["period"]

    assert client.get(f"/attendance/photo/{attendance_id}", headers=faculty).status_code == 200
    assert client.get(f"/attendance/photo/{attendance_id}", headers=student).status_code == 403
    admin_records = client.get("/admin/attendance/records", headers=admin)
    assert admin_records.status_code == 200
    evidence = next(r for r in admin_records.json() if r["id"] == attendance_id)
    assert evidence["has_photo"] is True and evidence["radius_meters"] == 50
    assert evidence["distance_meters"] is not None

    register = client.get("/faculty/attendance-register", headers=faculty).json()
    assert any(r["course_code"] == "ATT101" for r in register)

    assert client.post(f"/attendance/{attendance_id}/correction", headers=faculty,
                       json={"status": "absent", "reason": "no"}).status_code == 422
    res = client.post(f"/attendance/{attendance_id}/correction", headers=faculty,
                      json={"status": "absent", "reason": "Left early"})
    assert res.status_code == 200
    assert res.json()["status"] == "absent"
    # The corrected record must remain correctable: the roster exposes the
    # record id even when the student is now absent.
    roster_after = client.get(f"/faculty/attendance/sessions/{session['id']}", headers=faculty).json()
    corrected = next(a for a in roster_after["absent"] if a["attendance_id"] == attendance_id)
    assert corrected["attendance_id"] == attendance_id
    back = client.post(f"/attendance/{attendance_id}/correction", headers=faculty,
                       json={"status": "present", "reason": "Correction was a mistake"})
    assert back.status_code == 200 and back.json()["status"] == "present"
    logs = client.get("/admin/audit-logs", headers=admin).json()
    assert any(l["action"] == "correct_attendance" for l in logs)


def test_student_cannot_open_session(faculty, student):
    assert client.get("/faculty/attendance/sessions", headers=student).status_code == 403
    assert client.post("/faculty/attendance/sessions", headers=student,
                       json={"course_id": 1, "latitude": 1, "longitude": 1}).status_code == 403


def test_qr_generation_other_faculty_forbidden(admin, faculty):
    lecturer_id = _lecturer_id(admin)
    assert client.post(f"/faculty/generate-qr/{lecturer_id + 999}/P1",
                       headers=faculty, json={}).status_code == 403


def test_student_cannot_read_other_data(student):
    assert client.get("/faculty/class-list", headers=student).status_code == 403
    assert client.get("/admin/attendance-report", headers=student).status_code == 403


# ── Assessments & results ───────────────────────────────────────────────────
def test_assessment_marks_and_release(admin, faculty, student):
    courses = client.get("/faculty/my-courses", headers=faculty).json()
    itc = next(c for c in courses if c["code"] == "ITC101")
    res = client.post("/assessments", headers=faculty, json={
        "course_id": itc["id"], "title": "Mid-semester Quiz", "component": "quiz", "max_score": 20,
    })
    assert res.status_code == 201, res.text
    assessment_id = res.json()["id"]

    assert client.post(f"/assessments/{assessment_id}/marks", headers=faculty, json={
        "marks": [{"student_id": 999999, "score": 10}]}).status_code == 400

    class_list = client.get("/faculty/class-list", headers=faculty).json()
    itc_list = next(c for c in class_list if c["course_code"] == "ITC101")
    sid = itc_list["students"][0]["id"]
    assert client.post(f"/assessments/{assessment_id}/marks", headers=faculty, json={
        "marks": [{"student_id": sid, "score": 17}]}).status_code == 200

    before = client.get("/student/results", headers=student).json()
    assert all(r["assessment"] != "Mid-semester Quiz" for r in before)

    assert client.post(f"/assessments/{assessment_id}/release", headers=faculty).status_code == 200
    after = client.get("/student/results", headers=student).json()
    released = next(r for r in after if r["assessment"] == "Mid-semester Quiz")
    assert released["score"] == 17
    # 17/20 = 85% falls in the seeded A band.
    assert released["grade"] == "A"

    assert client.post("/assessments", headers=student, json={
        "course_id": itc["id"], "title": "x"}).status_code == 403


def test_grading_bands_admin(admin):
    bands = client.get("/admin/grading-bands", headers=admin).json()
    assert len(bands) >= 1
    res = client.post("/admin/grading-bands", headers=admin,
                      json={"name": "Z", "min_score": 0, "max_score": 1})
    assert res.status_code == 201
    assert client.delete(f"/admin/grading-bands/{res.json()['id']}", headers=admin).status_code == 200


# ── Announcements, notifications, audit, settings ───────────────────────────
def test_announcement_creation(admin):
    res = client.post("/announcements", headers=admin, json={
        "title": "Semester resumption", "body": "Classes begin Monday.", "audience": "students"})
    assert res.status_code == 201, res.text
    assert res.json()["recipients"] >= 1
    assert client.get("/announcements", headers=admin).status_code == 200


def test_student_sees_only_relevant_announcements(admin, faculty, student):
    # A faculty-only notice must not reach students; a students notice must.
    client.post("/announcements", headers=admin, json={
        "title": "Staff meeting", "audience": "lecturers"})
    client.post("/announcements", headers=admin, json={
        "title": "Fee deadline", "body": "Pay by Friday.", "audience": "students"})
    assert client.get("/student/announcements", headers=faculty).status_code == 403
    res = client.get("/student/announcements", headers=student)
    assert res.status_code == 200, res.text
    titles = [a["title"] for a in res.json()]
    assert "Fee deadline" in titles
    assert "Staff meeting" not in titles
    assert all("author" in a for a in res.json())


def test_notifications_flow(student):
    res = client.get("/notifications", headers=student)
    assert res.status_code == 200
    assert "items" in res.json()
    assert client.post("/notifications/read-all", headers=student).status_code == 200


def test_audit_log_populated(admin):
    res = client.get("/admin/audit-logs", headers=admin)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_faculty_cannot_read_audit_logs(faculty):
    assert client.get("/admin/audit-logs", headers=faculty).status_code == 403


def test_settings_round_trip(admin):
    original = client.get("/admin/settings", headers=admin).json()
    updated = {**original, "attendance_gps_radius_meters": 75}
    assert client.put("/admin/settings", headers=admin, json=updated).status_code == 200
    assert client.get("/admin/settings", headers=admin).json()["attendance_gps_radius_meters"] == 75
    assert "institution_name" not in client.get("/admin/settings", headers=admin).json()


def test_password_change_and_login(admin):
    res = client.put("/me/password", headers=admin,
                     json={"current_password": ADMIN[1], "new_password": "TempPass@123"})
    assert res.status_code == 200
    res = client.post("/login", json={"email": ADMIN[0], "password": "TempPass@123", "selected_role": "admin"})
    assert res.status_code == 200
    new_token = res.json()["access_token"]
    assert client.put("/me/password", headers={"Authorization": f"Bearer {new_token}"},
                      json={"current_password": "TempPass@123", "new_password": ADMIN[1]}).status_code == 200


# ── Materials ───────────────────────────────────────────────────────────────
def test_learning_materials_flow(admin, faculty, student):
    courses = client.get("/faculty/my-courses", headers=faculty).json()
    course_id = courses[0]["id"]
    res = client.post("/academic/materials", headers=faculty, json={
        "course_id": course_id, "title": "Week 1 slides",
        "url": "https://example.com/w1.pdf", "material_type": "document",
    })
    assert res.status_code == 201, res.text
    material_id = res.json()["id"]
    updated = client.put(f"/academic/materials/{material_id}", headers=faculty, json={
        "title": "Week 1 slides (revised)", "description": "Updated notes",
        "url": "https://example.com/w1-v2.pdf", "material_type": "note",
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "Week 1 slides (revised)"
    listed = client.get(f"/academic/materials?course_id={course_id}", headers=faculty).json()
    assert any(m["id"] == material_id and m["title"] == "Week 1 slides (revised)" for m in listed)
    assert client.put(f"/academic/materials/{material_id}", headers=student, json={
        "title": "hacked"}).status_code == 403
    assert client.delete(f"/academic/materials/{material_id}", headers=faculty).status_code == 200
    assert client.post("/academic/materials", headers=student, json={
        "course_id": course_id, "title": "x"}).status_code == 403


# ── Realtime & legacy ───────────────────────────────────────────────────────
def test_realtime_stream_requires_token():
    assert client.get("/events").status_code in (401, 403, 422)
    assert client.get("/events?token=garbage").status_code in (401, 403)


def test_legacy_face_endpoints_removed(admin):
    assert client.post("/student/register-face", headers=admin, json={}).status_code in (404, 405)
    from sqlalchemy import inspect as sa_inspect
    from database import engine
    columns = {c["name"] for c in sa_inspect(engine).get_columns("users")}
    assert "face_registered" not in columns


def test_institution_setup_routes_are_not_exposed():
    for path in ("/admin/structure/faculties", "/admin/structure/venues",
                 "/admin/structure/programmes", "/admin/structure/departments",
                 "/admin/structure/sessions", "/admin/structure/overview"):
        assert client.get(path).status_code == 404


def test_admin_attendance_summary_shape(admin):
    res = client.get("/admin/attendance-summary", headers=admin)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_course_deletion_guarded(admin):
    courses = client.get("/academic/courses", headers=admin).json()
    course = next(c for c in courses if c["code"] == "ATT101")
    assert client.delete(f"/academic/courses/{course['id']}", headers=admin).status_code == 409


def test_admin_list_shapes_include_editable_fields(admin):
    """Regression: GET /admin/students and /admin/faculty must expose the same
    fields the admin tables render and the edit modal pre-fills, so created
    records can actually be viewed and edited."""
    s = client.post("/admin/students", headers=admin, json={
        "name": "Shape Check Student", "index_number": "SHAPE-001",
        "email": "shape.student@example.com", "password": "Student@12345",
        "institution_name": "Shape University", "faculty_name": "Faculty of Science",
        "department": "Computer Science", "programme_name": "BSc. Shape",
        "academic_year": "2025/2026", "level": 200,
        "interests": "Testing", "is_approved": True}).json()
    listed = next(x for x in client.get("/admin/students", headers=admin).json()
                  if x["id"] == s["id"])
    for field in ("institution_name", "faculty_name", "department", "programme_name",
                  "academic_year", "level", "interests", "is_approved", "identity_status"):
        assert field in listed, f"students list is missing '{field}'"
    assert listed["institution_name"] == "Shape University"
    assert listed["academic_year"] == "2025/2026"

    f = client.post("/admin/faculty", headers=admin, json={
        "name": "Shape Check Lecturer", "email": "shape.lecturer@example.com",
        "password": "Lecturer@12345", "staff_id": "SHAPE-STF-1",
        "institution_name": "Shape University", "faculty_name": "Faculty of Science",
        "department": "Computer Science", "programme_name": "BSc. Shape",
        "designation": "Senior Lecturer", "is_approved": True}).json()
    listed_f = next(x for x in client.get("/admin/faculty", headers=admin).json()
                    if x["id"] == f["id"])
    for field in ("staff_id", "institution_name", "faculty_name", "department",
                  "programme_name", "designation", "is_approved", "identity_status"):
        assert field in listed_f, f"faculty list is missing '{field}'"
    assert listed_f["staff_id"] == "SHAPE-STF-1"
    assert listed_f["designation"] == "Senior Lecturer"

    client.delete(f"/admin/students/{s['id']}", headers=admin)
    client.delete(f"/admin/faculty/{f['id']}", headers=admin)


def _unique_selfie_b64() -> str:
    """A distinct valid PNG so the anti-replay guard does not reject it."""
    from PIL import Image
    import random
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def test_attendance_rate_consistent_across_student_surfaces(admin, faculty, student):
    """The dashboard percentage and the attendance page must never disagree.

    Both are the share of classes *held* that the student attended, so the
    "present / total" figures and the percentage have to match exactly.
    """
    course = _make_today_course(admin, faculty, "CONS101", "P4")
    batch = course["batches"][0]
    assert client.post("/academic/enrol", headers=student,
                       json={"course_id": course["id"], "batch_id": batch["id"],
                             "registration_code": course["registration_code"]}).status_code == 200

    opened = client.post("/faculty/attendance/sessions", headers=faculty, json={
        "course_id": course["id"], "period": "P4",
        "latitude": 5.115, "longitude": -1.289, "accuracy": 10}).json()
    assert client.post("/student/attendance/mark", headers=student, json={
        "token": opened["token"], "image": _unique_selfie_b64(),
        "latitude": 5.115, "longitude": -1.289, "accuracy": 10}).status_code == 200

    dash = client.get("/student/attendance-percentage", headers=student).json()
    page = client.get("/student/attendance/records", headers=student).json()["overall"]
    assert dash["total_classes"] == page["total"]
    assert dash["present_classes"] == page["present"]
    assert dash["percentage"] == page["rate"]
    assert page["present"] <= page["total"]

    per_course = next(c for c in client.get("/student/attendance/records",
                                            headers=student).json()["summary"]
                      if c["course_code"] == "CONS101")
    assert per_course["total"] == 1 and per_course["present"] == 1 and per_course["rate"] == 100.0


def test_session_opens_with_coarse_laptop_gps_fix(admin, faculty):
    """The reported GPS failure: a laptop without a GPS chip reports a coarse
    (high-accuracy) fix. Opening attendance must still succeed as long as the
    fix is usable; proximity is judged by distance against the session radius,
    not by the reported accuracy radius."""
    lecturer_id = _lecturer_id(admin)
    course = client.post("/academic/courses", headers=faculty, json={
        "title": "Coarse GPS Course", "code": "GPS901", "lecturer_id": lecturer_id,
        "programme_id": client.get("/public/academic-directory").json()["programmes"][0]["id"],
        "credit_hours": 1, "is_published": True, "registration_open": True,
    }).json()
    # A coarse but usable fix (well inside the session ceiling) must open.
    opened = client.post("/faculty/attendance/sessions", headers=faculty, json={
        "course_id": course["id"], "latitude": 5.650, "longitude": -0.187,
        "accuracy": 220, "radius_meters": 200, "session_minutes": 10})
    assert opened.status_code == 201, opened.text
    # A fix so imprecise the coordinates are meaningless is still rejected.
    rejected = client.post("/faculty/attendance/sessions", headers=faculty, json={
        "course_id": course["id"], "latitude": 5.650, "longitude": -0.187,
        "accuracy": 400})
    assert rejected.status_code == 400


def test_session_geofence_uses_distance_not_accuracy(admin, faculty, student):
    """A student with a coarse fix who is physically inside the radius is
    accepted; distance, not accuracy, decides proximity."""
    course = _make_today_course(admin, faculty, "GEOF501", "P6")
    batch = course["batches"][0]
    assert client.post("/academic/enrol", headers=student,
                       json={"course_id": course["id"], "batch_id": batch["id"],
                             "registration_code": course["registration_code"]}).status_code == 200
    opened = client.post("/faculty/attendance/sessions", headers=faculty, json={
        "course_id": course["id"], "period": "P6",
        "latitude": 5.6500, "longitude": -0.1870, "accuracy": 30,
        "radius_meters": 150}).json()
    # ~15 m away with a coarse 90 m accuracy reading: inside the radius.
    marked = client.post("/student/attendance/mark", headers=student, json={
        "token": opened["token"], "image": _unique_selfie_b64(),
        "latitude": 5.6501, "longitude": -0.1871, "accuracy": 90})
    assert marked.status_code == 200, marked.text

