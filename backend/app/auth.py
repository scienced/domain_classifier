"""
Authentication middleware and utilities
"""
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
import jwt
from .config import settings


security = HTTPBearer()


def create_access_token(data: dict) -> str:
    """
    Create JWT access token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=settings.AUTH_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.AUTH_TOKEN_SECRET,
        algorithm="HS256"
    )
    return encoded_jwt


def verify_password(password: str) -> bool:
    """
    Verify password against configured password
    """
    return password == settings.AUTH_PASSWORD


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """
    Verify JWT token and return payload
    """
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.AUTH_TOKEN_SECRET,
            algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Dependency for protected routes
async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """
    FastAPI dependency to protect routes
    """
    return verify_token(credentials)
