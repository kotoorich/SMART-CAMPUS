"""Server-Sent Events hub, notification fan-out and audit logging.

The application exposes a single ``/events`` SSE stream. Every connected client
receives events addressed to its user id or to its role, so data that changes in
one portal (for example a course created by an administrator, or a timetable
published) is pushed to the affected portals without a manual page refresh.

The hub is intentionally dependency-free: it keeps an in-memory registry of
connected clients. Sync (non-async) route handlers publish through
``publish_sync`` which schedules the delivery onto the running event loop.
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

# ── Event bus ────────────────────────────────────────────────────────────────
_loop: Optional[asyncio.AbstractEventLoop] = None
# connection id -> asyncio.Queue
_clients: dict[int, asyncio.Queue] = {}
# connection id -> {"user_id": int, "role": str}
_client_meta: dict[int, dict] = {}
_next_id = 1


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def register_client(user_id: int, role: str) -> tuple[int, asyncio.Queue]:
    global _next_id
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    cid = _next_id
    _next_id += 1
    _clients[cid] = queue
    _client_meta[cid] = {"user_id": user_id, "role": role}
    return cid, queue


def unregister_client(cid: int) -> None:
    _clients.pop(cid, None)
    _client_meta.pop(cid, None)


def _matches(meta: dict, user_ids: Optional[Iterable[int]], roles: Optional[Iterable[str]]) -> bool:
    if user_ids is None and roles is None:
        return True
    if user_ids is not None and meta.get("user_id") in set(user_ids):
        return True
    if roles is not None and meta.get("role") in set(roles):
        return True
    return False


def _deliver(event: dict, user_ids=None, roles=None) -> None:
    payload = json.dumps(event, default=str)
    for cid, queue in list(_clients.items()):
        if _matches(_client_meta.get(cid, {}), user_ids, roles):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                # Slow consumer — drop the oldest event so the stream stays live.
                try:
                    queue.get_nowait()
                    queue.put_nowait(payload)
                except Exception:
                    pass


def publish_sync(event_type: str, data: Any = None, *, user_ids=None, roles=None) -> None:
    """Publish from a synchronous route handler."""
    event = {"type": event_type, "data": data, "at": datetime.utcnow().isoformat()}
    if _loop is None or _loop.is_closed():
        return
    try:
        _loop.call_soon_threadsafe(_deliver, event, user_ids, roles)
    except RuntimeError:
        pass


async def event_stream(cid: int, queue: asyncio.Queue):
    """Yield SSE frames for one connected client."""
    try:
        yield "retry: 3000\n\n"
        yield "event: connected\ndata: {\"type\": \"connected\"}\n\n"
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=25)
                yield f"event: message\ndata: {payload}\n\n"
            except asyncio.TimeoutError:
                # Heartbeat keeps proxies and browsers from closing the stream.
                yield ": keep-alive\n\n"
    finally:
        unregister_client(cid)


# ── Notifications & audit ────────────────────────────────────────────────────

def notify(db: Session, user_id: int, title: str, body: str = "", category: str = "general", link: str = "") -> None:
    from models import Notification

    db.add(Notification(user_id=user_id, title=title, body=body, category=category, link=link))
    db.commit()
    publish_sync("notification", {"title": title, "body": body, "category": category, "link": link}, user_ids=[user_id])


def notify_many(db: Session, user_ids: Iterable[int], title: str, body: str = "", category: str = "general", link: str = "") -> None:
    from models import Notification

    ids = list({int(uid) for uid in user_ids})
    if not ids:
        return
    for uid in ids:
        db.add(Notification(user_id=uid, title=title, body=body, category=category, link=link))
    db.commit()
    publish_sync("notification", {"title": title, "body": body, "category": category, "link": link}, user_ids=ids)


def audit(db: Session, actor, action: str, entity: str = "", entity_id: Any = "", detail: str = "") -> None:
    from models import AuditLog

    db.add(AuditLog(
        actor_id=getattr(actor, "id", None),
        actor_name=getattr(actor, "name", None),
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        detail=detail,
    ))
    db.commit()
