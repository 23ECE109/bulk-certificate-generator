"""
Certificate download endpoint:
  GET /certificates/{certificate_id}/download  – stream the PDF file
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Certificate, CertificateStatus

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.get(
    "/{certificate_id}/download",
    summary="Download a generated certificate PDF",
    response_class=FileResponse,
)
def download_certificate(certificate_id: str, db: Session = Depends(get_db)):
    """
    Stream the generated PDF for the given certificate ID.

    Returns 404 if the certificate does not exist.
    Returns 409 if generation has not succeeded yet (still pending / failed).
    """
    cert: Certificate | None = db.get(Certificate, certificate_id)
    if cert is None:
        raise HTTPException(status_code=404, detail="Certificate not found")

    if cert.status != CertificateStatus.SUCCESS:
        raise HTTPException(
            status_code=409,
            detail=f"Certificate is not ready (status: {cert.status.value})",
        )

    if not cert.file_path or not Path(cert.file_path).exists():
        raise HTTPException(
            status_code=500,
            detail="Certificate file is missing from storage",
        )

    filename = f"certificate_{cert.recipient_name.replace(' ', '_')}.pdf"
    return FileResponse(
        path=cert.file_path,
        media_type="application/pdf",
        filename=filename,
    )
