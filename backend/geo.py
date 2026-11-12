"""Location and clock helpers shared by the attendance workflow.

Kept dependency-free of the application routers so both ``main`` and the
attendance router can import it without creating a circular import.
"""
from __future__ import annotations

import os
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2, isfinite
from zoneinfo import ZoneInfo

from fastapi import HTTPException

GPS_RADIUS_METERS = int(os.getenv("ATTENDANCE_GPS_RADIUS_METERS", "50"))
# A browser location fix can legitimately report a large accuracy radius indoors
# (commonly 30-80 m, sometimes worse). Validation only rejects fixes that are so
# imprecise the coordinates are meaningless; proximity is then judged by the
# haversine distance against the session radius, and the reported accuracy is
# stored as evidence rather than used to block a check-in.
#
# Opening a session only needs to anchor a reference point, so it tolerates a
# looser fix than a student check-in. A lecturer whose browser reports a coarse
# (but usable) fix must still be able to start attendance; the anchor quality is
# surfaced to students through the distance/accuracy evidence instead.
GPS_ACCURACY_CEILING = float(os.getenv("ATTENDANCE_GPS_ACCURACY_CEILING", "500"))
GPS_SESSION_ACCURACY_CEILING = float(
    os.getenv("ATTENDANCE_GPS_SESSION_ACCURACY_CEILING", str(max(300.0, GPS_ACCURACY_CEILING)))
)
APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Africa/Accra"))
DEV_ALLOW_ANY_TIME = (
    os.getenv("DEV_ALLOW_ANY_TIME", "false").lower() == "true"
    and os.getenv("ENVIRONMENT", "development").lower() != "production"
)


def app_now() -> datetime:
    return datetime.now(APP_TIMEZONE).replace(tzinfo=None)


def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlam = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlam / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def validated_gps(payload: dict, ceiling: float | None = None):
    """Validate latitude/longitude/accuracy, returning them as floats.

    ``ceiling`` overrides the maximum tolerated accuracy radius. Session
    creation passes a looser ceiling than a student check-in because anchoring a
    reference point does not need the same precision as verifying proximity.
    """
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
        raise HTTPException(400, "GPS accuracy is too weak to verify attendance. Turn on Location Services, allow precise location, move near a window or outdoors, and retry.")
    return latitude, longitude, accuracy
