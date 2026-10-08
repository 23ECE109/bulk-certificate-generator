"""
Bulk Certificate Generator – FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.routers import certificates, jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the database on startup."""
    init_db()
    yield


app = FastAPI(
    title="Bulk Certificate Generator",
    description=(
        "API for generating PDF certificates in bulk for event or course participants. "
        "Submit a list of recipients and track the generation progress."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(jobs.router)
app.include_router(certificates.router)


@app.get("/health", tags=["health"])
def health_check():
    """Simple liveness probe."""
    return {"status": "ok"}
