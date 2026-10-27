"""
Passwords and login tokens.

Passwords are stored only as bcrypt hashes. Logging in returns a signed token (a JWT) that the
frontend sends back as `Authorization: Bearer <token>`; endpoints under /users/{user_id} check
that the token belongs to that user.

Set JWT_SECRET (any long random string) in Project/backend/.env and on Render. Without it a random
secret is made at startup, so every restart logs everyone out.
"""

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from .database import get_session
from .models import User

log = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    log.warning("JWT_SECRET is not set; using a random one, so logins end when the server restarts.")
    JWT_SECRET = secrets.token_urlsafe(32)
JWT_ALGORITHM = "HS256"
TOKEN_LIFETIME = timedelta(days=30)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:  # accounts made before login existed have no password
        return False
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + TOKEN_LIFETIME
    return jwt.encode({"sub": str(user_id), "exp": expires}, JWT_SECRET, algorithm=JWT_ALGORITHM)


# auto_error=False so a missing token gives our own 401 instead of FastAPI's 403
bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    """The logged-in user, from the Bearer token. 401 if the token is missing, invalid or expired."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not logged in", headers={"WWW-Authenticate": "Bearer"})
    try:
        user_id = int(jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Your login has expired; please log in again",
                            headers={"WWW-Authenticate": "Bearer"})
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Account not found; please log in again",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


CurrentUserDep = Annotated[User, Depends(current_user)]


def require_owner(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[Session, Depends(get_session)],
    user_id: int | None = None,
):
    """
    For endpoints with a `user_id` (in the path, or the optional query parameter): only that user's
    token may use them. Endpoints where user_id is optional and left out stay open to everyone.
    """
    if user_id is None:
        return
    if current_user(credentials, session).id != user_id:
        raise HTTPException(status_code=403, detail="You can only access your own account")


OwnerOnly = Depends(require_owner)
