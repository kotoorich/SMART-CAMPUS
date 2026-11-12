"""Notification centre and audit log endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from deps import require_admin
from models import Notification, AuditLog, User
from realtime import publish_sync

router = APIRouter(tags=["notifications"])


def _notification_dict(n: Notification):
    return {"id": n.id, "title": n.title, "body": n.body, "category": n.category,
            "link": n.link, "is_read": n.is_read, "created_at": n.created_at.isoformat()}


@router.get("/notifications")
def list_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Notification).filter(Notification.user_id == user.id).order_by(
        Notification.created_at.desc()).limit(50).all()
    unread = db.query(Notification).filter(Notification.user_id == user.id,
                                           Notification.is_read == False).count()
    return {"unread": unread, "items": [_notification_dict(n) for n in rows]}


@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(Notification).filter(Notification.id == notification_id,
                                        Notification.user_id == user.id).first()
    if not row:
        raise HTTPException(404, "Notification not found")
    row.is_read = True
    db.commit()
    return {"message": "Marked read"}


@router.post("/notifications/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.user_id == user.id,
                                  Notification.is_read == False).update({"is_read": True})
    db.commit()
    publish_sync("notification_read", {}, user_ids=[user.id])
    return {"message": "All notifications marked read"}


@router.get("/admin/audit-logs")
def audit_logs(_: User = Depends(require_admin), db: Session = Depends(get_db), limit: int = 200):
    limit = max(1, min(limit, 1000))
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [{"id": a.id, "actor_name": a.actor_name, "action": a.action, "entity": a.entity,
             "entity_id": a.entity_id, "detail": a.detail, "created_at": a.created_at.isoformat()}
            for a in rows]
