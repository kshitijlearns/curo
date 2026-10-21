"""GET /v1/jobs/{id} — job progress for the app.

Stands in locally for Supabase Realtime on the jobs table (DECISIONS D2). RLS limits it to
the creator's own jobs.
"""

from __future__ import annotations

from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from curo.routes.deps import rls_conn
from curo.schemas.api import JobOut

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: UUID, conn: psycopg.Connection = Depends(rls_conn)) -> JobOut:
    row = conn.execute("select * from public.jobs where id = %s", (job_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return JobOut(**row)
