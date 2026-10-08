"""
Tests for certificate download endpoint and individual failure handling.
"""

import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.conftest import VALID_JOB_PAYLOAD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_job_and_get_certs(client: TestClient, payload=None):
    payload = payload or VALID_JOB_PAYLOAD
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    certs = client.get(f"/jobs/{job_id}/certificates").json()
    return job_id, certs


# ---------------------------------------------------------------------------
# GET /certificates/{id}/download
# ---------------------------------------------------------------------------


class TestDownloadCertificate:
    def test_download_returns_pdf(self, client: TestClient):
        _, certs = _create_job_and_get_certs(client)
        success_cert = next(c for c in certs if c["status"] == "success")
        resp = client.get(f"/certificates/{success_cert['id']}/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"

    def test_download_content_is_pdf_bytes(self, client: TestClient):
        _, certs = _create_job_and_get_certs(client)
        success_cert = next(c for c in certs if c["status"] == "success")
        resp = client.get(f"/certificates/{success_cert['id']}/download")
        # PDF files start with the magic bytes %PDF
        assert resp.content[:4] == b"%PDF"

    def test_download_404_for_unknown_certificate(self, client: TestClient):
        resp = client.get("/certificates/does-not-exist/download")
        assert resp.status_code == 404

    def test_download_409_for_failed_certificate(self, client: TestClient):
        """A certificate whose generation failed should return 409."""
        # Simulate a failure by patching generate_certificate to raise
        from app import certificate_generator

        with patch.object(
            certificate_generator,
            "generate_certificate",
            side_effect=RuntimeError("disk full"),
        ):
            payload = {
                **VALID_JOB_PAYLOAD,
                "recipients": [{"name": "Failure User", "email": "fail@example.com"}],
            }
            job_id = client.post("/jobs", json=payload).json()["job_id"]

        certs = client.get(f"/jobs/{job_id}/certificates").json()
        failed_cert = certs[0]
        assert failed_cert["status"] == "failed"

        resp = client.get(f"/certificates/{failed_cert['id']}/download")
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Individual failure handling
# ---------------------------------------------------------------------------


class TestIndividualFailureHandling:
    def test_one_failure_does_not_prevent_others(self, client: TestClient):
        """
        When one recipient's generation fails, the rest should still succeed.
        """
        from app import certificate_generator

        call_count = {"n": 0}
        original_fn = certificate_generator.generate_certificate

        def _fail_first_call(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise ValueError("Simulated generation error for first recipient")
            original_fn(**kwargs)

        with patch.object(certificate_generator, "generate_certificate", _fail_first_call):
            payload = {
                **VALID_JOB_PAYLOAD,
                "recipients": [
                    {"name": "Will Fail", "email": "fail@example.com"},
                    {"name": "Will Succeed", "email": "ok@example.com"},
                    {"name": "Also Succeeds", "email": "ok2@example.com"},
                ],
            }
            job_id = client.post("/jobs", json=payload).json()["job_id"]

        detail = client.get(f"/jobs/{job_id}").json()
        assert detail["succeeded"] == 2
        assert detail["failed_count"] == 1
        # Job should be COMPLETED (not FAILED) because at least one succeeded
        assert detail["status"] == "completed"

    def test_all_failures_marks_job_failed(self, client: TestClient):
        """When every certificate fails the job status becomes 'failed'."""
        from app import certificate_generator

        with patch.object(
            certificate_generator,
            "generate_certificate",
            side_effect=RuntimeError("catastrophic failure"),
        ):
            job_id = client.post("/jobs", json=VALID_JOB_PAYLOAD).json()["job_id"]

        detail = client.get(f"/jobs/{job_id}").json()
        assert detail["status"] == "failed"
        assert detail["succeeded"] == 0
        assert detail["failed_count"] == 2

    def test_failed_certificate_records_error_message(self, client: TestClient):
        """The error_message field on a failed cert should be populated."""
        from app import certificate_generator

        with patch.object(
            certificate_generator,
            "generate_certificate",
            side_effect=RuntimeError("test error message"),
        ):
            payload = {
                **VALID_JOB_PAYLOAD,
                "recipients": [{"name": "Error User", "email": "err@example.com"}],
            }
            job_id = client.post("/jobs", json=payload).json()["job_id"]

        certs = client.get(f"/jobs/{job_id}/certificates").json()
        assert certs[0]["error_message"] is not None
        assert "test error message" in certs[0]["error_message"]


# ---------------------------------------------------------------------------
# Certificate generation unit tests
# ---------------------------------------------------------------------------


class TestCertificateGeneration:
    def test_generate_creates_pdf_file(self, tmp_path):
        from app.certificate_generator import generate_certificate

        output = str(tmp_path / "test_cert.pdf")
        generate_certificate(
            output_path=output,
            recipient_name="Jane Doe",
            event_name="Test Event",
            issued_by="Test Org",
            issue_date="2024-11-15",
        )
        import os
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_generate_pdf_has_magic_bytes(self, tmp_path):
        from app.certificate_generator import generate_certificate

        output = str(tmp_path / "test_cert.pdf")
        generate_certificate(
            output_path=output,
            recipient_name="John Doe",
            event_name="Advanced Python",
            issued_by="Acme Corp",
            issue_date="2024-06-01",
        )
        with open(output, "rb") as f:
            header = f.read(4)
        assert header == b"%PDF"

    def test_generate_creates_parent_directory(self, tmp_path):
        from app.certificate_generator import generate_certificate

        output = str(tmp_path / "nested" / "deeply" / "cert.pdf")
        generate_certificate(
            output_path=output,
            recipient_name="Dir Test",
            event_name="Event",
            issued_by="Org",
            issue_date="2024-01-01",
        )
        import os
        assert os.path.exists(output)
