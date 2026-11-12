from sqlalchemy import create_engine
from pathlib import Path
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# ── Use Supabase PostgreSQL on production, SQLite locally ─────────────────────
BASE_DIR = Path(__file__).resolve().parent
_default_db = (BASE_DIR / "smart_campus.db").as_posix()
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_default_db}").strip()

# Render and Supabase both hand out "postgres://" URLs, which SQLAlchemy 2.0 no
# longer accepts. Normalise the scheme before the engine is created.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# requirements.txt installs psycopg2-binary (the psycopg2 driver). SQLAlchemy
# otherwise defaults postgresql:// to psycopg (v3), which is not installed and
# causes Render to crash during startup with: ModuleNotFoundError: psycopg.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg2://", 1
    )

# SQLite needs check_same_thread=False, PostgreSQL does not.
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    # pool_pre_ping + recycle keep long-lived connections healthy on managed
    # Postgres (Supabase) that close idle connections. sslmode is only added
    # when the URL does not already specify it.
    connect_args = {}
    if "sslmode=" not in DATABASE_URL and "localhost" not in DATABASE_URL \
            and "127.0.0.1" not in DATABASE_URL:
        connect_args["sslmode"] = "require"
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args=connect_args,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()