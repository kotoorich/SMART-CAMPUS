"""Secure private storage for attendance selfie photographs.

The API must not fail to boot merely because a Render Persistent Disk is
missing or mounted read-only. STORAGE_DIR is preferred, then the Render disk,
then a writable temporary directory. Temporary storage is ephemeral; configure
a persistent Render disk for long-term selfie retention.
"""
from __future__ import annotations

import logging
import os
import re
import secrets
import tempfile
from pathlib import Path

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _is_writable_directory(path: Path) -> bool:
    """Check real write access (os.access alone can be misleading as root)."""
    probe = path / f".write-check-{secrets.token_hex(8)}"
    try:
        with probe.open("xb") as handle:
            handle.write(b"ok")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def _initialise_store_dir() -> Path:
    """Choose the first writable private storage directory."""
    is_render = os.environ.get("RENDER", "").lower() == "true"
    candidates: list[Path] = []

    configured_dir = os.environ.get("STORAGE_DIR", "").strip()
    if configured_dir:
        candidates.append(Path(configured_dir).expanduser())

    if is_render:
        candidates.append(Path("/var/data/smart-campus/attendance"))

    # Always retain a fallback. This also handles a configured STORAGE_DIR
    # pointing to an unavailable mount and Render environments where RENDER
    # is not injected for some reason.
    candidates.append(Path(tempfile.gettempdir()) / "smart-campus" / "attendance")

    if not is_render:
        candidates.append(
            Path(__file__).resolve().parent / "private_uploads" / "attendance"
        )

    seen: set[str] = set()
    last_error: OSError | None = None
    for candidate in candidates:
        candidate = candidate.resolve()
        if str(candidate) in seen:
            continue
        seen.add(str(candidate))
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            if not _is_writable_directory(candidate):
                raise PermissionError(f"Storage directory is not writable: {candidate}")

            if is_render and candidate == Path(tempfile.gettempdir()).resolve() / "smart-campus" / "attendance":
                logger.warning(
                    "Render Persistent Disk is unavailable; using temporary storage at %s. "
                    "Attendance selfies may be lost after a restart or redeploy. "
                    "Attach a writable disk at /var/data or set STORAGE_DIR to a writable path.",
                    candidate,
                )
            return candidate
        except OSError as exc:
            last_error = exc
            logger.warning("Cannot use attendance storage directory %s: %s", candidate, exc)

    raise RuntimeError(
        "No writable private attendance storage directory is available. "
        "Set STORAGE_DIR to a writable directory or attach a writable Render Persistent Disk."
    ) from last_error


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
