
import jwt

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Recruiter
from app.auth.security import decode_access_token


# HTTP Bearer authentication
# Swagger will now show a simple token input field.
bearer_scheme = HTTPBearer()


def get_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """
    Extract JWT access token from the Authorization header.
    """
    return credentials.credentials


def get_current_recruiter(
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
) -> Recruiter:
    """
    Validate JWT and retrieve the authenticated recruiter.
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)

        recruiter_id = payload.get("sub")

        if not recruiter_id:
            raise credentials_exception

        recruiter_id = int(recruiter_id)

    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise credentials_exception

    recruiter = (
        db.query(Recruiter)
        .filter(Recruiter.id == recruiter_id)
        .first()
    )

    if recruiter is None or not recruiter.is_active:
        raise credentials_exception

    return recruiter
