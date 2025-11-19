"""
Authentication API routes
"""
from fastapi import APIRouter, HTTPException, status

from ..schemas.schemas import LoginRequest, LoginResponse
from ..auth import verify_password, create_access_token

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Login with password and receive JWT token
    """
    if not verify_password(request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password"
        )

    # Create access token
    access_token = create_access_token({"sub": "user"})

    return LoginResponse(access_token=access_token)
