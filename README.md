# Bulk Certificate Generator

A FastAPI backend that accepts bulk certificate generation requests, generates PDF certificates from a predefined template, and lets clients track progress and download the results.

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [Setup](#setup)
3. [Running the Application](#running-the-application)
4. [Running the Tests](#running-the-tests)
5. [API Usage](#api-usage)
   - [Create a Generation Job](#create-a-generation-job)
   - [Check Job Status](#check-job-status)
   - [List Certificates for a Job](#list-certificates-for-a-job)
   - [Download a Certificate](#download-a-certificate)
6. [Design Decisions](#design-decisions)

---

## Project Structure

```
aereo_1/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, lifespan, router registration
│   ├── config.py                # Settings (database URL, certificates dir)
│   ├── database.py              # SQLAlchemy engine, session factory, init_db
│   ├── models.py                # ORM models: Job, Certificate
│   ├── schemas.py               # Pydantic request/response schemas
│   ├── certificate_generator.py # PDF generation with ReportLab
│   ├── worker.py                # Background thread-pool worker
│   └── routers/
│       ├── __init__.py
│       ├── jobs.py              # POST /jobs, GET /jobs/{id}, GET /jobs/{id}/certificates
│       └── certificates.py     # GET /certificates/{id}/download
├── certificates/                # Generated PDF files (created at runtime)
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures, test DB setup
│   ├── test_jobs.py             # Tests for job creation, validation, status
│   └── test_certificates.py    # Tests for download, failure handling, PDF generation
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.11 or 3.12
- `pip`

### Install dependencies

```bash
pip install -r requirements.txt
```

This installs FastAPI, SQLAlchemy, ReportLab, Pydantic, pytest, and supporting libraries.

### Configuration (optional)

The application uses sensible defaults (SQLite file at `./certificates.db`, PDFs stored in `./certificates/`). You can override these with environment variables or a `.env` file:

```env
DATABASE_URL=sqlite:///./certificates.db
CERTIFICATES_DIR=./certificates
```

---

## Running the Application

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

Interactive API documentation (Swagger UI) is at: `http://127.0.0.1:8000/docs`

---

## Running the Tests

```bash
pytest
```

Or with verbose output:

```bash
pytest -v
```

The test suite uses an isolated file-based SQLite database (in a temp directory) and patches the background worker to run synchronously, so tests are deterministic and leave no state behind.

---

## API Usage

### Create a Generation Job

**POST** `/jobs`

Submit a list of recipients and queue PDF certificate generation for all of them. The request returns immediately with a `job_id` (HTTP 202 Accepted).

**Request body:**

```json
{
  "event_name": "Python Masterclass 2024",
  "issued_by": "Acme Academy",
  "issue_date": "2024-11-15",
  "recipients": [
    { "name": "Alice Smith",  "email": "alice@example.com" },
    { "name": "Bob Jones",    "email": "bob@example.com"   },
    { "name": "Carol White",  "email": "carol@example.com" }
  ]
}
```

| Field        | Type   | Required | Notes |
|--------------|--------|----------|-------|
| `event_name` | string | yes | Name of the event or course |
| `issued_by`  | string | yes | Issuing organisation or person |
| `issue_date` | string | yes | ISO date format `YYYY-MM-DD` |
| `recipients` | array  | yes | At least one recipient required |
| `recipients[].name`  | string | yes | Non-blank full name |
| `recipients[].email` | string | yes | Valid email address |

**Response (202):**

```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "message": "Job accepted. Generating certificates for 3 recipient(s)."
}
```

**cURL example:**

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "Python Masterclass 2024",
    "issued_by": "Acme Academy",
    "issue_date": "2024-11-15",
    "recipients": [
      {"name": "Alice Smith", "email": "alice@example.com"},
      {"name": "Bob Jones",   "email": "bob@example.com"}
    ]
  }'
```

---

### Check Job Status

**GET** `/jobs/{job_id}`

Returns the current status of the job and the status of every certificate.

**Possible job statuses:**

| Status       | Meaning |
|--------------|---------|
| `pending`    | Queued, not started yet |
| `processing` | Currently generating certificates |
| `completed`  | Finished; at least one certificate succeeded |
| `failed`     | Finished; every certificate failed |

**Response (200):**

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "event_name": "Python Masterclass 2024",
  "issued_by": "Acme Academy",
  "issue_date": "2024-11-15",
  "status": "completed",
  "total": 2,
  "succeeded": 2,
  "failed_count": 0,
  "created_at": "2024-11-15T10:00:00Z",
  "updated_at": "2024-11-15T10:00:05Z",
  "certificates": [
    {
      "id": "cert-uuid-1",
      "job_id": "3fa85f64-...",
      "recipient_name": "Alice Smith",
      "recipient_email": "alice@example.com",
      "status": "success",
      "error_message": null,
      "created_at": "...",
      "updated_at": "..."
    }
  ]
}
```

---

### List Certificates for a Job

**GET** `/jobs/{job_id}/certificates`

Returns the list of certificate records for a job without the full job detail.

```bash
curl http://localhost:8000/jobs/{job_id}/certificates
```

---

### Download a Certificate

**GET** `/certificates/{certificate_id}/download`

Streams the generated PDF file.

- Returns **200** with `Content-Type: application/pdf` when the certificate is ready.
- Returns **409** if the certificate is still pending or failed.
- Returns **404** if the certificate ID does not exist.

```bash
curl -O certificate_alice.pdf \
  http://localhost:8000/certificates/{certificate_id}/download
```

---

## Design Decisions

### Background Processing: `ThreadPoolExecutor`

The certificate generation work (PDF rendering + disk I/O) is offloaded to a `ThreadPoolExecutor` with 4 workers. The POST `/jobs` endpoint returns immediately (HTTP 202) and the client polls for status.

**Why not `FastAPI BackgroundTasks`?**  
`BackgroundTasks` runs the callback in the same thread that handled the request, which would block uvicorn's threadpool for the entire duration of a large batch.

**Why not Celery / RQ?**  
A full task queue adds significant operational complexity (Redis/broker setup, worker processes, deployment). For a single-service take-home this is unnecessary overhead. The README acknowledges this as the right next step for production.

**Why not async + `asyncio.to_thread`?**  
This would work but adds complexity without clear benefit since the certificate generation and SQLAlchemy operations are all synchronous. The thread pool keeps everything simple and easy to reason about.

### Synchronous SQLAlchemy (not async)

All database access uses synchronous SQLAlchemy sessions. This is consistent with the synchronous thread-pool worker design and avoids the extra complexity of `aiosqlite` + async SQLAlchemy.

### Database: SQLite (default)

SQLite requires no external service, making the project trivially easy to run. The `DATABASE_URL` setting can be changed to PostgreSQL for production without any code changes.

### Certificate Template

A single A4-landscape PDF template is rendered entirely with ReportLab primitives (no external image assets required). Each certificate includes:
- Double gold border
- "CERTIFICATE OF COMPLETION" heading
- Recipient name (large, centred, underlined)
- Event name
- Issuer name and date

### Failure Isolation

Each certificate is generated in its own `try/except` block inside the worker. A failure marks only that certificate as `failed` (with the error message stored) and continues to the next one. The job status is `completed` if at least one certificate succeeded, `failed` only if all failed.

### Input Validation

Pydantic validators on `RecipientIn` and `JobCreateRequest` enforce:
- Non-blank names (strips whitespace and rejects blank strings)
- Valid email format (`EmailStr` via `email-validator`)
- ISO date format for `issue_date`
- At least one recipient per request

Invalid requests return HTTP 422 with field-level error detail before any DB writes occur.
