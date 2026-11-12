from datetime import datetime, timedelta, timezone
import os
import secrets
import tempfile
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from models import User

# Render sets RENDER=true automatically. Treat hosted Render instances as
# production even when the operator has not added a separate ENVIRONMENT flag.
IS_PRODUCTION = (
    os.getenv("RENDER", "").lower() == "true"
    or os.getenv("ENVIRONMENT", "development").lower() == "production"
)

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise RuntimeError("Set JWT_SECRET_KEY in the Render service environment.")
    backend_dir = Path(__file__).resolve().parent
    secret_file = backend_dir / ".jwt_secret"
    try:
        if secret_file.exists():
            SECRET_KEY = secret_file.read_text(encoding="utf-8").strip()
        if not SECRET_KEY:
            SECRET_KEY = secrets.token_urlsafe(64)
            fd, temporary_name = tempfile.mkstemp(prefix=".jwt_secret.", dir=backend_dir)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(SECRET_KEY)
                os.replace(temporary_name, secret_file)
            finally:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)
        os.environ["JWT_SECRET_KEY"] = SECRET_KEY
    except OSError as exc:
        raise RuntimeError(
            "Cannot persist the development JWT secret. Set JWT_SECRET_KEY in backend/.env."
        ) from exc

if SECRET_KEY in {"supersecretkey", "replace-with-a-long-random-secret"}:
    raise RuntimeError("Insecure default JWT secret is not allowed")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 720
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user
