"""Shared FastAPI dependencies for role-based access control."""
from fastapi import Depends, HTTPException

from auth import get_current_user
from models import User


def require_roles(*roles):
    """Return a dependency that only allows the listed roles."""
    def check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "You do not have permission to perform this action")
        return user
    return check


require_admin = require_roles("admin")
require_faculty = require_roles("faculty")
require_admin_or_faculty = require_roles("admin", "faculty")
require_student = require_roles("student")
