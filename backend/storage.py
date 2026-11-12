"""Private attendance and registration photo storage.

Production uses a private Supabase Storage bucket. Local development can use
private local files when Supabase credentials are not configured. The Supabase
service-role key stays on the backend and is never exposed to the browser.
"""
from __future__ import annotations

import base64
import logging
import os
import re
import secrets
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from fastapi import HTTPException

logger = logging.getLogger(__name__)

MAX_BYTES = 5 * 1024 * 1024
_EXT_BY_FORMAT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
_KEY_RE = re.compile(r"^[A-Za-z0-9]{8,64}(?:\.(?:jpg|png|webp))?$")


def _storage_config():
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "attendance-selfies").strip()
    if bool(url) != bool(service_key):
        raise RuntimeError("Configure both SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
    requested = os.getenv("STORAGE_BACKEND", "").strip().lower()
    if requested and requested not in {"supabase", "local"}:
        raise RuntimeError("STORAGE_BACKEND must be either 'supabase' or 'local'.")
    if requested == "supabase" and not (url and service_key):
        raise RuntimeError("STORAGE_BACKEND=supabase requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
    if os.getenv("RENDER", "").lower() == "true" and not (url and service_key):
        raise RuntimeError(
            "Production photo storage is not configured. Set SUPABASE_URL, "
            "SUPABASE_SERVICE_ROLE_KEY and SUPABASE_STORAGE_BUCKET in Render."
        )
    use_supabase = requested == "supabase" or (not requested and bool(url and service_key))
    return use_supabase, url, service_key, bucket


USE_SUPABASE, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_STORAGE_BUCKET = _storage_config()


def _initialise_local_store() -> Path:
    configured = os.getenv("STORAGE_DIR", "").strip()
    candidates = [Path(configured).expanduser()] if configured else []
    candidates.append(Path(tempfile.gettempdir()) / "smart-campus" / "attendance")
    candidates.append(Path(__file__).resolve().parent / "private_uploads" / "attendance")
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / f".write-check-{secrets.token_hex(8)}"
            with probe.open("xb") as handle:
                handle.write(b"ok")
            probe.unlink(missing_ok=True)
            return candidate
        except OSError as exc:
            logger.warning("Cannot use local photo storage %s: %s", candidate, exc)
    raise RuntimeError("No writable local photo storage directory is available.")


STORE_DIR = None if USE_SUPABASE else _initialise_local_store()


def _decode_base64_image(data: str) -> bytes:
    payload = data.strip()
    if payload.startswith("data:"):
        comma = payload.find(",")
        if comma == -1:
            raise HTTPException(400, "Malformed image data URL")
        payload = payload[comma + 1:]
    try:
        return base64.b64decode(payload, validate=True)
    except Exception:
        raise HTTPException(400, "The photo could not be decoded. Retake and try again.")


def _detect_and_validate(raw: bytes) -> str:
    if not raw:
        raise HTTPException(400, "The photo is empty")
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "The photo is too large (maximum 5 MB)")
    try:
        from io import BytesIO
        from PIL import Image
        with Image.open(BytesIO(raw)) as image:
            fmt = (image.format or "").upper()
    except Exception:
        raise HTTPException(400, "The photo is not a valid image (JPEG, PNG or WebP required)")
    if fmt not in _EXT_BY_FORMAT:
        raise HTTPException(400, "Unsupported image type. Use JPEG, PNG or WebP.")
    return fmt


def _supabase_request(method: str, object_path: str, raw: bytes | None = None,
                      content_type: str | None = None) -> bytes:
    bucket = urllib.parse.quote(SUPABASE_STORAGE_BUCKET, safe="")
    encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in object_path.split("/"))
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{encoded_path}"
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    if method == "POST":
        headers["x-upsert"] = "false"
    request = urllib.request.Request(url, data=raw, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        # Do not leak credentials or raw provider response bodies into logs/API errors.
        if exc.code == 404:
            raise HTTPException(404, "Stored photo not found") from exc
        logger.error("Supabase Storage request failed with HTTP %s (%s).", exc.code, method)
        raise HTTPException(503, "Photo storage is temporarily unavailable. Please try again.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("Supabase Storage connection failed (%s): %s", method, type(exc).__name__)
        raise HTTPException(503, "Photo storage is temporarily unavailable. Please try again.") from exc


def save_selfie(data: str) -> str:
    """Validate and persist a selfie, returning its opaque storage object path."""
    raw = _decode_base64_image(data)
    fmt = _detect_and_validate(raw)
    extension = _EXT_BY_FORMAT[fmt]
    key = secrets.token_urlsafe(24).replace("-", "").replace("_", "") + extension
    if USE_SUPABASE:
        _supabase_request("POST", key, raw, f"image/{'jpeg' if fmt == 'JPEG' else fmt.lower()}")
    else:
        assert STORE_DIR is not None
        (STORE_DIR / key).write_bytes(raw)
    return key


def read_selfie(image_ref: str) -> tuple[bytes, str]:
    """Read a private image and return its bytes plus MIME type."""
    if not image_ref or not _KEY_RE.fullmatch(image_ref):
        raise HTTPException(404, "Attendance photo not found")
    suffix = Path(image_ref).suffix.lower()
    if suffix not in {".jpg", ".png", ".webp"}:
        # Legacy local references did not include the extension.
        if USE_SUPABASE:
            raise HTTPException(404, "Attendance photo not found")
        assert STORE_DIR is not None
        for ext in _EXT_BY_FORMAT.values():
            candidate = STORE_DIR / f"{image_ref}{ext}"
            if candidate.is_file():
                suffix = ext
                break
        else:
            raise HTTPException(404, "Attendance photo not found")
        image_ref = f"{image_ref}{suffix}"
    if USE_SUPABASE:
        raw = _supabase_request("GET", image_ref)
    else:
        assert STORE_DIR is not None
        candidate = STORE_DIR / image_ref
        if not candidate.is_file():
            raise HTTPException(404, "Attendance photo not found")
        raw = candidate.read_bytes()
    media_type = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}[suffix]
    return raw, media_type


def delete_selfie(image_ref: str) -> None:
    if not image_ref or not _KEY_RE.fullmatch(image_ref):
        return
    try:
        if USE_SUPABASE:
            _supabase_request("DELETE", image_ref)
        else:
            assert STORE_DIR is not None
            (STORE_DIR / image_ref).unlink(missing_ok=True)
    except HTTPException:
        # Cleanup is best-effort; the primary database/payment error is preserved.
        logger.warning("Could not delete a photo object during cleanup.")
