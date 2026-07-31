from fastapi import APIRouter
from app.services.user_service import UserService
from app.core.dependencies import get_user_service
from app.schemas.user_schema import UserList, UserCreate
from app.core.response import ApiResponse
from fastapi import Depends

router = APIRouter()

@router.get("/users")
async def index(request: UserList = Depends(), service: UserService=Depends(get_user_service)):
    return ApiResponse.success(data=service.list_users(request))

@router.get("/users/{id}")
async def show(id: int, service: UserService=Depends(get_user_service)):
    return ApiResponse.success(data=service.get_user(id))

@router.post("/users")
async def store(request: UserCreate, service: UserService = Depends(get_user_service)):
    return ApiResponse.success(data = service.create_user(request))