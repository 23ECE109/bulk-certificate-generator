"""
SQLAlchemy ORM models.

Two tables:
- Job          : represents a bulk certificate generation request
- Certificate  : one row per recipient inside a job
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"          # all recipients failed


class CertificateStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_name = Column(String(255), nullable=False)
    issued_by = Column(String(255), nullable=False)
    issue_date = Column(String(20), nullable=False)   # ISO date string, e.g. "2024-11-15"

    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.PENDING)
    total = Column(Integer, nullable=False, default=0)
    succeeded = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)  # column name avoids clash

    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    certificates = relationship(
        "Certificate", back_populates="job", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Certificate
# ---------------------------------------------------------------------------


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)

    recipient_name = Column(String(255), nullable=False)
    recipient_email = Column(String(255), nullable=False)

    status = Column(Enum(CertificateStatus), nullable=False, default=CertificateStatus.PENDING)
    file_path = Column(Text, nullable=True)   # absolute path on disk once generated
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    job = relationship("Job", back_populates="certificates")
