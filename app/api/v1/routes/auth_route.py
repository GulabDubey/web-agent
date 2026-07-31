from fastapi import APIRouter, Depends
from app.schemas.auth_schema import LoginRequest
from app.services.auth_service import AuthService
from app.core.dependencies import get_auth_service

router = APIRouter(    
    prefix="/auth",
    tags=["Authentication"]
)

@router.post("/login")
async def login(request: LoginRequest, auth_service: AuthService = Depends(get_auth_service)):
    return auth_service.login_user(request)
