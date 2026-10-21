"""Uploads for the Simulator (MVP doc §7: ``POST /v1/uploads/sign``).

The app asks for a signed URL and sends the video straight to storage. With local storage
the signed URL is this API's ``PUT /v1/uploads/local/{token}``; with Supabase it is
Supabase's own. Uploads live under ``uploads/{creator id}/`` in the videos bucket.

A video provider may offer sample recordings (the mock offers the demo's two takes, real
providers none): ``GET /v1/uploads/samples`` lists them and ``POST /v1/uploads/sample``
stores one as if it had been uploaded.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from curo import providers
from curo.config import get_settings
from curo.providers.storage.base import StorageError
from curo.routes.deps import require_creator, rls_conn
from curo.schemas.api import SampleIn, SampleVideo, Uploaded, UploadSigned, UploadSignIn
from curo.services import mp4

router = APIRouter(prefix="/v1/uploads", tags=["uploads"])

EXTENSIONS = {"video/mp4": "mp4", "video/quicktime": "mov"}
MAX_UPLOAD_BYTES = 300 * 1024 * 1024  # a 90-second phone recording is well under this


def upload_prefix(creator_id) -> str:
    return f"uploads/{creator_id}/"


@router.post("/sign", response_model=UploadSigned)
def sign(body: UploadSignIn, conn: psycopg.Connection = Depends(rls_conn)) -> UploadSigned:
    creator = require_creator(conn)
    path = f"{upload_prefix(creator['id'])}{uuid.uuid4().hex}.{EXTENSIONS[body.content_type]}"
    try:
        signed = providers.get_storage().signed_upload(
            get_settings().storage_bucket_videos, path, body.content_type
        )
    except NotImplementedError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Uploads aren’t set up on this server yet."
        ) from exc
    return UploadSigned(
        path=path,
        url=signed.url,
        method=signed.method,
        headers=signed.headers,
        expires_at=signed.expires_at,
    )


@router.put("/local/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def receive(token: str, request: Request) -> Response:
    """Local storage's signed upload URL. The token is the permission: it names one path and
    expires (like Supabase's signed upload URLs, no sign-in header is needed)."""
    length = request.headers.get("content-length")
    if length and int(length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "That file is too large.")
    data = await request.body()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "That file is too large.")
    try:
        providers.get_storage().accept_upload(token, data)
    except StorageError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/samples", response_model=list[SampleVideo])
def samples(conn: psycopg.Connection = Depends(rls_conn)) -> list[SampleVideo]:
    require_creator(conn)
    return [SampleVideo(**asdict(s)) for s in providers.get_video().samples()]


@router.post("/sample", response_model=Uploaded, status_code=status.HTTP_201_CREATED)
def sample(body: SampleIn, conn: psycopg.Connection = Depends(rls_conn)) -> Uploaded:
    creator = require_creator(conn)
    video = providers.get_video()
    found = next((s for s in video.samples() if s.name == body.name), None)
    data = video.sample_file(body.name) if found else None
    if found is None or data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No sample recording by that name.")
    meta = mp4.check(data)
    path = f"{upload_prefix(creator['id'])}{uuid.uuid4().hex}.mp4"
    providers.get_storage().put(get_settings().storage_bucket_videos, path, data, "video/mp4")
    return Uploaded(
        path=path,
        duration_s=meta.duration_s,
        width=meta.width,
        height=meta.height,
        caption=found.caption,
    )
