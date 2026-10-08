"""
Pydantic schemas for request / response validation and serialisation.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class RecipientIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Full name of the recipient")
    email: EmailStr = Field(..., description="Email address of the recipient")

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("name must not be blank or whitespace only")
        return stripped


class JobCreateRequest(BaseModel):
    event_name: str = Field(
        ..., min_length=1, max_length=255, description="Name of the event or course"
    )
    issued_by: str = Field(
        ..., min_length=1, max_length=255, description="Issuing organisation or person"
    )
    issue_date: str = Field(
        ..., description="Date to print on certificate (YYYY-MM-DD)"
    )
    recipients: List[RecipientIn] = Field(
        ..., min_length=1, description="List of recipients (at least one required)"
    )

    @field_validator("issue_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        from datetime import date
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("issue_date must be a valid ISO date string (YYYY-MM-DD)")
        return v

    @field_validator("event_name", "issued_by")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be blank or whitespace only")
        return stripped


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class CertificateOut(BaseModel):
    id: str
    job_id: str
    recipient_name: str
    recipient_email: str
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: str
    event_name: str
    issued_by: str
    issue_date: str
    status: str
    total: int
    succeeded: int
    failed_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobDetailOut(JobOut):
    certificates: List[CertificateOut] = []

    model_config = {"from_attributes": True}


class JobCreateResponse(BaseModel):
    job_id: str
    message: str
