"""Idempotent, additive schema migrations for Smart Campus.

The project uses SQLAlchemy ``create_all`` to create any *new* tables, and this
module to evolve *existing* tables in place. Every step is written to be safe to
run repeatedly and to preserve existing rows — no migration drops user data.

Steps
-----
1. ``add_missing_columns`` — ADD COLUMN for every column introduced since the
   original schema (SQLite and PostgreSQL both support this).
2. ``retire_face_column`` — drop the retired ``users.face_registered`` column.
3. ``rebuild_attendance_for_sessions`` — the original ``attendance`` table had a
   ``UNIQUE(student_id, date, period)`` constraint that prevented a student from
   being marked present in two different courses sharing a period. SQLite cannot
   drop a constraint in place, so the table is rebuilt and its rows copied
   verbatim before the old table is removed.
4. ``backfill_registration_code_expiry`` — codes seeded before the expiry column
   existed would read as expired; only NULL expiries are touched.

Call ``run_migrations()`` once at application start-up (see ``main.py``).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import inspect, text

from database import engine

# ── (table, column, DDL type) added over the life of the project ─────────────
_ADDED_COLUMNS = [
    ("nep_courses", "platform", "VARCHAR"),
    ("nep_courses", "description", "VARCHAR"),
    ("qr_sessions", "token", "VARCHAR"),
    ("qr_sessions", "course_id", "INTEGER"),
    ("users", "section", "VARCHAR"),
    ("faculties", "institution_name", "VARCHAR DEFAULT 'University of Cape Coast'"),
    ("departments", "institution_name", "VARCHAR DEFAULT 'University of Cape Coast'"),
    ("programmes", "institution_name", "VARCHAR DEFAULT 'University of Cape Coast'"),
    ("users", "index_number", "VARCHAR"),
    ("users", "department_id", "INTEGER"),
    ("users", "programme_id", "INTEGER"),
    ("users", "level", "INTEGER"),
    ("users", "phone", "VARCHAR"),
    ("users", "institution_name", "VARCHAR"),
    ("users", "faculty_name", "VARCHAR"),
    ("users", "programme_name", "VARCHAR"),
    ("users", "academic_year", "VARCHAR"),
    ("users", "designation", "VARCHAR"),
    ("users", "staff_id", "VARCHAR"),
    ("users", "ghana_card_hash", "VARCHAR"),
    ("users", "ghana_card_last4", "VARCHAR"),
    ("users", "identity_document_type", "VARCHAR"),
    ("users", "identity_document_hash", "VARCHAR"),
    ("users", "identity_document_last4", "VARCHAR"),
    ("users", "registration_photo_ref", "VARCHAR"),
    ("users", "biometric_method", "VARCHAR"),
    ("users", "identity_status", "VARCHAR DEFAULT 'pending'"),
    ("users", "registration_fee_required", "BOOLEAN DEFAULT 0"),
    ("courses", "registration_code_expires_at", "TIMESTAMP"),
    ("courses", "programme_id", "INTEGER"),
    ("courses", "institution_name", "VARCHAR"),
    ("courses", "programme_name", "VARCHAR"),
    ("courses", "department_id", "INTEGER"),
    ("courses", "credit_hours", "INTEGER"),
    ("courses", "is_published", "BOOLEAN DEFAULT 0"),
    ("faculty_schedule", "course_id", "INTEGER"),
    ("faculty_schedule", "venue_id", "INTEGER"),
    ("faculty_schedule", "batch_id", "INTEGER"),
    ("faculty_schedule", "academic_session_id", "INTEGER"),
    ("faculty_schedule", "is_published", "BOOLEAN DEFAULT 0"),
    # Session-scoped attendance (selfie workflow) and course-batch enrolment.
    ("attendance", "marked_at", "TIMESTAMP"),
    ("attendance", "attendance_points", "FLOAT"),
    ("attendance_sessions", "access_code", "VARCHAR"),
    ("attendance_sessions", "radius_meters", "INTEGER"),
    ("attendance", "course_id", "INTEGER"),
    ("attendance", "attendance_session_id", "INTEGER"),
    ("attendance", "batch_id", "INTEGER"),
    ("attendance", "academic_session_id", "INTEGER"),
    ("attendance", "method", "VARCHAR DEFAULT 'SELFIE'"),
    ("attendance", "image_ref", "VARCHAR"),
    ("attendance", "image_sha256", "VARCHAR"),
    ("attendance", "latitude", "FLOAT"),
    ("attendance", "longitude", "FLOAT"),
    ("attendance", "gps_accuracy", "FLOAT"),
    ("attendance", "distance_meters", "FLOAT"),
    ("attendance", "note", "VARCHAR"),
    ("course_enrolments", "batch_id", "INTEGER"),
    ("course_enrolments", "withdrawn_at", "TIMESTAMP"),
    ("course_enrolments", "withdrawal_reason", "VARCHAR"),
    ("learning_materials", "batch_id", "INTEGER"),
]


def add_missing_columns() -> None:
    tables = set(inspect(engine).get_table_names())
    with engine.begin() as conn:
        for table, column, ddl in _ADDED_COLUMNS:
            if table not in tables:
                continue
            existing = {col["name"] for col in inspect(engine).get_columns(table)}
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def retire_face_column() -> None:
    if "users" not in inspect(engine).get_table_names():
        return
    existing = {col["name"] for col in inspect(engine).get_columns("users")}
    if "face_registered" not in existing:
        return
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.execute(text("ALTER TABLE users DROP COLUMN face_registered"))
        else:
            conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS face_registered"))


def rebuild_attendance_for_sessions() -> None:
    if "attendance" not in inspect(engine).get_table_names():
        return
    columns = {c["name"] for c in inspect(engine).get_columns("attendance")}

    if engine.dialect.name != "sqlite":
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE attendance DROP CONSTRAINT IF EXISTS uq_attendance_student_date_period"
            ))
        return

    with engine.begin() as conn:
        ddl = conn.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='attendance'"
        )).scalar() or ""
    if "uq_attendance_student_date_period" not in ddl:
        return

    target = [
        "id", "student_id", "faculty_id", "attendance_session_id", "course_id",
        "batch_id", "academic_session_id", "date", "period", "status", "method",
        "marked_by", "image_ref", "image_sha256", "latitude", "longitude", "gps_accuracy", "distance_meters",
        "note", "marked_at", "attendance_points",
    ]
    present = [c for c in target if c in columns]
    cols = ", ".join(present)
    select_cols = ", ".join(
        "COALESCE(method, 'SELFIE')" if c == "method"
        else "COALESCE(marked_at, CURRENT_TIMESTAMP)" if c == "marked_at"
        else c for c in present
    )
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE attendance_new ("
            " id INTEGER NOT NULL PRIMARY KEY,"
            " student_id INTEGER NOT NULL, faculty_id INTEGER NOT NULL,"
            " attendance_session_id INTEGER, course_id INTEGER, batch_id INTEGER,"
            " academic_session_id INTEGER, date VARCHAR NOT NULL, period VARCHAR NOT NULL,"
            " status VARCHAR NOT NULL, method VARCHAR, marked_by VARCHAR, image_ref VARCHAR,"
            " latitude FLOAT, longitude FLOAT, note VARCHAR, marked_at TIMESTAMP NOT NULL, attendance_points FLOAT,"
            " CONSTRAINT uq_attendance_student_session UNIQUE (student_id, attendance_session_id))"
        ))
        conn.execute(text(f"INSERT INTO attendance_new ({cols}) SELECT {select_cols} FROM attendance"))
        conn.execute(text("DROP TABLE attendance"))
        conn.execute(text("ALTER TABLE attendance_new RENAME TO attendance"))
        for index_col in ("student_id", "attendance_session_id", "course_id", "batch_id"):
            conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS ix_attendance_{index_col} ON attendance ({index_col})"
            ))


def backfill_registration_code_expiry() -> None:
    if "courses" not in inspect(engine).get_table_names():
        return
    if "registration_code_expires_at" not in {c["name"] for c in inspect(engine).get_columns("courses")}:
        return
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE courses SET registration_code_expires_at = :exp "
            "WHERE registration_code IS NOT NULL AND registration_code != '' "
            "AND registration_code_expires_at IS NULL"
        ), {"exp": datetime.utcnow() + timedelta(days=365)})


def add_identity_indexes() -> None:
    """Enforce uniqueness for newly introduced identity fields on old databases."""
    tables = set(inspect(engine).get_table_names())
    if "users" not in tables:
        return
    columns = {c["name"] for c in inspect(engine).get_columns("users")}
    with engine.begin() as conn:
        if "staff_id" in columns:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_staff_id ON users (staff_id)"))
        if "ghana_card_hash" in columns:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_ghana_card_hash ON users (ghana_card_hash)"))
        if "identity_document_hash" in columns:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_identity_document_hash ON users (identity_document_hash)"))
    if "attendance_sessions" in tables:
        session_columns = {c["name"] for c in inspect(engine).get_columns("attendance_sessions")}
        if "access_code" in session_columns:
            with engine.begin() as conn:
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_sessions_access_code ON attendance_sessions (access_code)"))



def backfill_academic_directory_links() -> None:
    """Link legacy free-text academic profiles to managed directory records."""
    tables = set(inspect(engine).get_table_names())
    if not {"users", "departments", "programmes", "courses"}.issubset(tables):
        return
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE users SET department_id = ("
            " SELECT d.id FROM departments d"
            " WHERE lower(trim(d.name)) = lower(trim(users.department)) LIMIT 1"
            ") WHERE department_id IS NULL AND department IS NOT NULL"
        ))
        conn.execute(text(
            "UPDATE users SET programme_id = ("
            " SELECT p.id FROM programmes p"
            " WHERE lower(trim(p.name)) = lower(trim(users.programme_name))"
            " AND (p.department_id = users.department_id OR users.department_id IS NULL)"
            " LIMIT 1"
            ") WHERE programme_id IS NULL AND programme_name IS NOT NULL"
        ))
        conn.execute(text(
            "UPDATE users SET department_id = ("
            " SELECT p.department_id FROM programmes p WHERE p.id = users.programme_id"
            ") WHERE department_id IS NULL AND programme_id IS NOT NULL"
        ))
        conn.execute(text(
            "UPDATE courses SET programme_id = ("
            " SELECT p.id FROM programmes p"
            " WHERE lower(trim(p.name)) = lower(trim(courses.programme_name))"
            " AND (p.department_id = courses.department_id OR courses.department_id IS NULL)"
            " LIMIT 1"
            ") WHERE programme_id IS NULL AND programme_name IS NOT NULL"
        ))
        conn.execute(text(
            "UPDATE courses SET department_id = ("
            " SELECT p.department_id FROM programmes p WHERE p.id = courses.programme_id"
            ") WHERE department_id IS NULL AND programme_id IS NOT NULL"
        ))


def run_migrations() -> None:
    """Apply every migration in order. Safe to call on every start-up."""
    add_missing_columns()
    backfill_directory_institutions()
    relax_global_directory_uniqueness()
    backfill_academic_directory_links()
    add_identity_indexes()
    retire_face_column()
    rebuild_attendance_for_sessions()
    backfill_registration_code_expiry()



def backfill_directory_institutions() -> None:
    """Keep legacy academic records visible while assigning them an institution."""
    tables = set(inspect(engine).get_table_names())
    if not {"faculties", "departments", "programmes"}.issubset(tables):
        return
    with engine.begin() as conn:
        for table in ("faculties", "departments", "programmes"):
            columns = {c["name"] for c in inspect(engine).get_columns(table)}
            if "institution_name" in columns:
                conn.execute(text(
                    "UPDATE " + table + " SET institution_name = 'University of Cape Coast' "
                    "WHERE institution_name IS NULL OR trim(institution_name) = ''"
                ))



def relax_global_directory_uniqueness() -> None:
    """Replace global directory-code uniqueness with institution-scoped indexes."""
    tables = set(inspect(engine).get_table_names())
    with engine.begin() as conn:
        for table, column in (
            ("faculties", "name"), ("faculties", "code"),
            ("departments", "code"), ("programmes", "code"), ("courses", "code"),
        ):
            if table not in tables:
                continue
            for index in inspect(engine).get_indexes(table):
                if index.get("unique") and index.get("column_names") == [column]:
                    conn.execute(text("DROP INDEX IF EXISTS " + index["name"]))
        index_sql = (
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_faculties_institution_name ON faculties (institution_name, name)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_faculties_institution_code ON faculties (institution_name, code)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_departments_institution_code ON departments (institution_name, code)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_programmes_institution_code ON programmes (institution_name, code)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_courses_institution_code ON courses (institution_name, code)",
        )
        for statement in index_sql:
            table = statement.split(" ON ", 1)[1].split(" ", 1)[0]
            if table in tables:
                conn.execute(text(statement))
