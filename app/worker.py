"""
Background certificate generation worker.

Design decision — synchronous thread pool
------------------------------------------
Generation is CPU-bound (PDF rendering) and involves local disk I/O, so
using Python's ThreadPoolExecutor keeps things straightforward:

* FastAPI's `BackgroundTasks` runs the submitted callable in the same event
  loop thread, which would block the server.  A ThreadPoolExecutor moves the
  work off the event loop entirely.

* asyncio + run_in_executor would also work but adds indirection without
  benefit here because the worker itself is purely synchronous.

* A dedicated task queue (Celery / RQ) would be appropriate for a
  production system that needs durability, retries, or horizontal scaling.
  That complexity is out of scope for this take-home; the README explains the
  trade-off.

Each job is processed by a single worker thread:
  1. Mark job as PROCESSING.
  2. Iterate over pending certificates; generate each one.
     - On success: mark certificate SUCCESS, write file_path.
     - On failure: mark certificate FAILED, write error_message.
       → other certificates continue.
  3. When all done, mark job COMPLETED (or FAILED if every cert failed).
"""

import os
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy.orm import Session

import app.certificate_generator as certificate_generator
from app.config import settings
from app.models import Certificate, CertificateStatus, Job, JobStatus

# Single shared thread pool; one thread is enough for demonstration purposes.
# Increase max_workers to process multiple jobs concurrently.
_executor = ThreadPoolExecutor(max_workers=4)


def submit_job(job_id: str, db_factory) -> None:
    """
    Submit a job for background processing.

    Parameters
    ----------
    job_id:     The UUID of the Job row.
    db_factory: A zero-argument callable that returns a new SQLAlchemy Session.
                Passing the factory (not the session) is important because
                sessions are NOT thread-safe.
    """
    _executor.submit(_process_job, job_id, db_factory)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _process_job(job_id: str, db_factory) -> None:
    """Entry point for the worker thread."""
    db: Session = db_factory()
    try:
        job: Job | None = db.get(Job, job_id)
        if job is None:
            return  # should not happen

        job.status = JobStatus.PROCESSING
        db.commit()

        certs = [c for c in job.certificates if c.status == CertificateStatus.PENDING]

        for cert in certs:
            _generate_one(cert, job, db)

        # Final job status
        db.refresh(job)
        if job.succeeded == 0:
            job.status = JobStatus.FAILED
        else:
            job.status = JobStatus.COMPLETED
        db.commit()

    except Exception:
        # Unexpected error in the worker itself — mark job failed
        try:
            db.rollback()
            job = db.get(Job, job_id)
            if job:
                job.status = JobStatus.FAILED
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _generate_one(cert: Certificate, job: Job, db: Session) -> None:
    """Generate a single certificate and update its row."""
    output_path = _cert_output_path(job.id, cert.id)
    try:
        certificate_generator.generate_certificate(
            output_path=output_path,
            recipient_name=cert.recipient_name,
            event_name=job.event_name,
            issued_by=job.issued_by,
            issue_date=job.issue_date,
        )
        cert.status = CertificateStatus.SUCCESS
        cert.file_path = output_path
        job.succeeded += 1
    except Exception as exc:
        cert.status = CertificateStatus.FAILED
        cert.error_message = f"{type(exc).__name__}: {exc}"
        job.failed_count += 1
    finally:
        db.commit()


def _cert_output_path(job_id: str, cert_id: str) -> str:
    """Return the absolute path for a certificate PDF."""
    directory = Path(settings.certificates_dir) / job_id
    return str(directory / f"{cert_id}.pdf")
