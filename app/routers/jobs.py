"""
Job endpoints:
  POST /jobs                          – create a bulk generation job
  GET  /jobs/{job_id}                 – get job status + per-cert summary
  GET  /jobs/{job_id}/certificates    – list certificates for a job
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import Certificate, CertificateStatus, Job, JobStatus
from app.schemas import (
    CertificateOut,
    JobCreateRequest,
    JobCreateResponse,
    JobDetailOut,
)
from app.worker import submit_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a bulk certificate generation job",
)
def create_job(payload: JobCreateRequest, db: Session = Depends(get_db)):
    """
    Accept a list of recipients and queue certificate generation.

    Returns the job ID immediately (HTTP 202).  The client can then poll
    GET /jobs/{job_id} to track progress.
    """
    # Create the Job row
    job = Job(
        event_name=payload.event_name,
        issued_by=payload.issued_by,
        issue_date=payload.issue_date,
        total=len(payload.recipients),
        status=JobStatus.PENDING,
    )
    db.add(job)
    db.flush()  # get the generated job.id before creating certificates

    # Create one Certificate row per recipient
    for recipient in payload.recipients:
        cert = Certificate(
            job_id=job.id,
            recipient_name=recipient.name,
            recipient_email=recipient.email,
            status=CertificateStatus.PENDING,
        )
        db.add(cert)

    db.commit()
    job_id = job.id
    total = job.total
    # Close the session BEFORE submitting the job so the worker can acquire
    # its own DB connection without contention (important for SQLite).
    db.close()

    # Submit to background worker (non-blocking)
    submit_job(job_id, SessionLocal)

    return JobCreateResponse(
        job_id=job_id,
        message=f"Job accepted. Generating certificates for {total} recipient(s).",
    )


@router.get(
    "/{job_id}",
    response_model=JobDetailOut,
    summary="Get job status and certificate list",
)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Return the job's current status plus the status of every certificate."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get(
    "/{job_id}/certificates",
    response_model=list[CertificateOut],
    summary="List all certificates for a job",
)
def list_certificates(job_id: str, db: Session = Depends(get_db)):
    """Return every certificate record belonging to the job."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.certificates
