import os
from contextlib import contextmanager
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()


def get_database_url() -> str:
    """
    Retrieves and normalizes the database connection URL.
    Supports Neon Serverless PostgreSQL with SQLAlchemy 2.0 + psycopg.
    Defaults to local SQLite for offline development if DATABASE_URL is not set.
    """
    url = os.getenv("DATABASE_URL", "").strip()

    if not url:
        # Fallback to local SQLite when DATABASE_URL is not yet configured
        return "sqlite:///./voice_interview.db"

    # Normalize Neon/PostgreSQL connection string for psycopg3
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    return url


DATABASE_URL = get_database_url()

is_sqlite = DATABASE_URL.startswith("sqlite")

engine_kwargs = {
    "pool_pre_ping": True,  # Critical for Neon serverless connections that can suspend/disconnect
}

if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL / Neon optimizations
    engine_kwargs["pool_recycle"] = 300
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    """FastAPI dependency for yielding database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager for internal operations with automatic commit/rollback."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
