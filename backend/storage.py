"""Secure storage for attendance selfie photographs.

Photos are written to a private directory outside any static/web root and are
never exposed as public URLs. Each stored file is addressed by an opaque random
key; the database only ever holds that key (Attendance.image_ref). Retrieval
goes through an authenticated endpoint that checks the caller is an authorised
lecturer or administrator, so a photograph cannot be fetched by guessing an id.

Files are validated for type (JPEG/PNG/WebP) and size before being written.
"""
from __future__ import annotations

import logging
import os
import re
import secrets
from pathlib import Path

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _initialise_store_dir() -> Path:
    """Choose a writable private storage path, with a safe Render fallback."""
    configured_dir = os.environ.get("STORAGE_DIR")
    is_render = os.environ.get("RENDER", "").lower() == "true"

    if configured_dir:
        candidates = [Path(configured_dir).expanduser()]
    elif is_render:
        candidates = [
            Path("/var/data/smart-campus/attendance"),
            Path("/tmp/smart-campus/attendance"),
        ]
    else:
        candidates = [
            Path(__file__).resolve().parent / "private_uploads" / "attendance"
        ]

    last_error: OSError | None = None
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            if not os.access(candidate, os.W_OK | os.X_OK):
                raise PermissionError(f"Storage directory is not writable: {candidate}")
            if is_render and str(candidate).startswith("/tmp/"):
                logger.warning(
                    "Render persistent storage is unavailable; using ephemeral %s. "
                    "Attendance selfies may be lost when the instance restarts. "
                    "Attach a persistent disk at /var/data or configure STORAGE_DIR.",
                    candidate,
                )
            return candidate
        except OSError as exc:
            last_error = exc
            logger.warning("Cannot use storage directory %s: %s", candidate, exc)

    raise RuntimeError(
        "No writable private attendance storage directory is available. "
        "Configure STORAGE_DIR to a writable path."
    ) from last_error


# STORAGE_DIR may be configured on any host. Render's persistent disk is
# preferred; without an attached/writable disk, /tmp keeps the API bootable.
# The /tmp fallback is ephemeral across restarts. For durable selfie storage,
# attach a Render disk and set STORAGE_DIR=/var/data/smart-campus/attendance.
STORE_DIR = _initialise_store_dir()

MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_EXT_BY_FORMAT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


def _decode_base64_image(data: str) -> bytes:
    """Decode a data URL or bare base64 string to raw bytes."""
    payload = data.strip()
    if payload.startswith("data:"):
        comma = payload.find(",")
        if comma == -1:
            raise HTTPException(400, "Malformed image data URL")
        payload = payload[comma + 1:]
    try:
        import base64
        return base64.b64decode(payload, validate=True)
    except Exception:
        raise HTTPException(400, "The attendance photo could not be decoded. Retake and try again.")


def _detect_and_validate(raw: bytes) -> str:
    if not raw:
        raise HTTPException(400, "The attendance photo is empty")
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "The attendance photo is too large (maximum 5 MB)")
    try:
        from io import BytesIO
        from PIL import Image
        with Image.open(BytesIO(raw)) as image:
            fmt = (image.format or "").upper()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "The attendance photo is not a valid image (JPEG, PNG or WebP required)")
    if fmt not in _EXT_BY_FORMAT:
        raise HTTPException(400, "Unsupported image type. Use JPEG, PNG or WebP.")
    return fmt


def save_selfie(data: str) -> str:
    """Validate and persist a selfie, returning its opaque storage key."""
    raw = _decode_base64_image(data)
    fmt = _detect_and_validate(raw)
    key = secrets.token_urlsafe(24).replace("-", "").replace("_", "")
    (STORE_DIR / f"{key}{_EXT_BY_FORMAT[fmt]}").write_bytes(raw)
    return key


_KEY_RE = re.compile(r"^[A-Za-z0-9]{8,64}$")


def resolve_path(image_ref: str) -> Path:
    """Return the on-disk path for a stored key, guarding against traversal."""
    if not image_ref or not _KEY_RE.match(image_ref):
        raise HTTPException(404, "Attendance photo not found")
    for ext in _EXT_BY_FORMAT.values():
        candidate = STORE_DIR / f"{image_ref}{ext}"
        if candidate.is_file():
            return candidate
    raise HTTPException(404, "Attendance photo not found")


def delete_selfie(image_ref: str) -> None:
    if not image_ref:
        return
    try:
        resolve_path(image_ref).unlink(missing_ok=True)
    except HTTPException:
        pass
