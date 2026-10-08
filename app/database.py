"""
Database session management.

Uses a synchronous SQLite engine (via SQLAlchemy Core).  All I/O in the
background worker is also synchronous to keep the implementation simple and
avoid the complexity of async SQLAlchemy with aiosqlite.

The engine / session factory are module-level singletons so that test code
can swap them out before importing the rest of the app.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings
from app.models import Base

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # needed for SQLite
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all tables if they don't already exist."""
    import app.database as _self
    Base.metadata.create_all(bind=_self.engine)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def get_db():
    """Yield a DB session and ensure it is closed afterwards."""
    import app.database as _self
    db: Session = _self.SessionLocal()
    try:
        yield db
    finally:
        db.close()
