"""Location and clock helpers shared by the attendance workflow."""
from __future__ import annotations

from datetime import datetime
import os
from math import radians, sin, cos, sqrt, atan2, isfinite
from zoneinfo import ZoneInfo

from fastapi import HTTPException

# Institution-facing attendance limits are configured in the Admin Settings
# screen. These are safe technical validation limits, not deployment settings.
GPS_RADIUS_METERS = 50
GPS_ACCURACY_CEILING = 300.0
GPS_SESSION_ACCURACY_CEILING = 300.0
APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Africa/Accra"))
DEV_ALLOW_ANY_TIME = (
    os.getenv("DEV_ALLOW_ANY_TIME", "false").lower() == "true"
    and os.getenv("RENDER", "").lower() != "true"
    and os.getenv("ENVIRONMENT", "development").lower() != "production"
)


def app_now() -> datetime:
    return datetime.now(APP_TIMEZONE).replace(tzinfo=None)


def haversine(lat1, lon1, lat2, lon2) -> float:
    radius = 6_371_000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlam = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlam / 2) ** 2
    return radius * 2 * atan2(sqrt(a), sqrt(1 - a))


def validated_gps(payload: dict, ceiling: float | None = None):
    """Validate GPS coordinates and accuracy before attendance verification."""
    try:
        latitude = float(payload.get("latitude"))
        longitude = float(payload.get("longitude"))
        accuracy = float(payload.get("accuracy"))
    except (TypeError, ValueError):
        raise HTTPException(400, "Valid latitude, longitude and GPS accuracy are required.")
    if not all(isfinite(value) for value in (latitude, longitude, accuracy)):
        raise HTTPException(400, "GPS coordinates and accuracy must be finite numbers.")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise HTTPException(400, "GPS coordinates are outside valid ranges.")
    limit = GPS_ACCURACY_CEILING if ceiling is None else ceiling
    if accuracy < 0 or accuracy > limit:
        raise HTTPException(
            400,
            "GPS accuracy is too weak to verify attendance. Turn on Location Services, "
            "allow precise location, move near a window or outdoors, and retry."
        )
    return latitude, longitude, accuracy
