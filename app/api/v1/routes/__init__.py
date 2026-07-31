from fastapi import APIRouter
from .chat_route import router as chat_router
from .user_route import router as user_router
from .auth_route import router as auth_router

router = APIRouter()

router.include_router(chat_router)
router.include_router(user_router)
router.include_router(auth_router)