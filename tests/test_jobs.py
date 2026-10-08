"""
Tests for job creation, status, and listing endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import VALID_JOB_PAYLOAD


# ---------------------------------------------------------------------------
# POST /jobs  – create a generation job
# ---------------------------------------------------------------------------


class TestCreateJob:
    def test_create_job_returns_202(self, client: TestClient):
        response = client.post("/jobs", json=VALID_JOB_PAYLOAD)
        assert response.status_code == 202

    def test_create_job_returns_job_id(self, client: TestClient):
        response = client.post("/jobs", json=VALID_JOB_PAYLOAD)
        body = response.json()
        assert "job_id" in body
        assert len(body["job_id"]) == 36  # UUID format

    def test_create_job_message_mentions_recipient_count(self, client: TestClient):
        response = client.post("/jobs", json=VALID_JOB_PAYLOAD)
        assert "2" in response.json()["message"]

    def test_create_job_processes_to_completed(self, client: TestClient):
        """With the synchronous worker patch the job should be COMPLETED."""
        job_id = client.post("/jobs", json=VALID_JOB_PAYLOAD).json()["job_id"]
        status_resp = client.get(f"/jobs/{job_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "completed"

    def test_create_single_recipient(self, client: TestClient):
        payload = {**VALID_JOB_PAYLOAD, "recipients": [{"name": "Solo User", "email": "solo@example.com"}]}
        response = client.post("/jobs", json=payload)
        assert response.status_code == 202

    def test_create_large_batch(self, client: TestClient):
        """50 recipients should all succeed."""
        recipients = [
            {"name": f"Recipient {i}", "email": f"r{i}@example.com"}
            for i in range(50)
        ]
        payload = {**VALID_JOB_PAYLOAD, "recipients": recipients}
        resp = client.post("/jobs", json=payload)
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]
        detail = client.get(f"/jobs/{job_id}").json()
        assert detail["succeeded"] == 50
        assert detail["failed_count"] == 0


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_missing_event_name(self, client: TestClient):
        payload = {k: v for k, v in VALID_JOB_PAYLOAD.items() if k != "event_name"}
        assert client.post("/jobs", json=payload).status_code == 422

    def test_missing_issued_by(self, client: TestClient):
        payload = {k: v for k, v in VALID_JOB_PAYLOAD.items() if k != "issued_by"}
        assert client.post("/jobs", json=payload).status_code == 422

    def test_empty_recipients_list(self, client: TestClient):
        payload = {**VALID_JOB_PAYLOAD, "recipients": []}
        assert client.post("/jobs", json=payload).status_code == 422

    def test_invalid_email(self, client: TestClient):
        payload = {
            **VALID_JOB_PAYLOAD,
            "recipients": [{"name": "Bad Email", "email": "not-an-email"}],
        }
        assert client.post("/jobs", json=payload).status_code == 422

    def test_blank_recipient_name(self, client: TestClient):
        payload = {
            **VALID_JOB_PAYLOAD,
            "recipients": [{"name": "   ", "email": "valid@example.com"}],
        }
        assert client.post("/jobs", json=payload).status_code == 422

    def test_invalid_issue_date(self, client: TestClient):
        payload = {**VALID_JOB_PAYLOAD, "issue_date": "15-11-2024"}
        assert client.post("/jobs", json=payload).status_code == 422

    def test_blank_event_name(self, client: TestClient):
        payload = {**VALID_JOB_PAYLOAD, "event_name": "   "}
        assert client.post("/jobs", json=payload).status_code == 422

    def test_missing_recipient_name(self, client: TestClient):
        payload = {
            **VALID_JOB_PAYLOAD,
            "recipients": [{"email": "nope@example.com"}],
        }
        assert client.post("/jobs", json=payload).status_code == 422


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}  – job status
# ---------------------------------------------------------------------------


class TestJobStatus:
    def test_status_404_for_unknown_job(self, client: TestClient):
        assert client.get("/jobs/nonexistent-id").status_code == 404

    def test_status_has_correct_totals(self, client: TestClient):
        job_id = client.post("/jobs", json=VALID_JOB_PAYLOAD).json()["job_id"]
        detail = client.get(f"/jobs/{job_id}").json()
        assert detail["total"] == 2
        assert detail["succeeded"] == 2
        assert detail["failed_count"] == 0

    def test_status_includes_certificate_list(self, client: TestClient):
        job_id = client.post("/jobs", json=VALID_JOB_PAYLOAD).json()["job_id"]
        detail = client.get(f"/jobs/{job_id}").json()
        assert len(detail["certificates"]) == 2

    def test_certificate_entries_have_expected_fields(self, client: TestClient):
        job_id = client.post("/jobs", json=VALID_JOB_PAYLOAD).json()["job_id"]
        certs = client.get(f"/jobs/{job_id}").json()["certificates"]
        for cert in certs:
            assert "id" in cert
            assert "status" in cert
            assert "recipient_name" in cert
            assert "recipient_email" in cert


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/certificates  – list certificates
# ---------------------------------------------------------------------------


class TestListCertificates:
    def test_list_returns_correct_count(self, client: TestClient):
        job_id = client.post("/jobs", json=VALID_JOB_PAYLOAD).json()["job_id"]
        resp = client.get(f"/jobs/{job_id}/certificates")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_404_for_unknown_job(self, client: TestClient):
        assert client.get("/jobs/bad-id/certificates").status_code == 404

    def test_list_contains_recipient_names(self, client: TestClient):
        job_id = client.post("/jobs", json=VALID_JOB_PAYLOAD).json()["job_id"]
        names = {c["recipient_name"] for c in client.get(f"/jobs/{job_id}/certificates").json()}
        assert "Alice Smith" in names
        assert "Bob Jones" in names
