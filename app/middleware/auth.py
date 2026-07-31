from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

class AuthMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request, call_next):

        token = request.headers.get("Authorization")

        if token != "Bearer secret":

            return JSONResponse(
                status_code=401,
                content={
                    "message": "Unauthorized"
                }
            )

        response = await call_next(request)

        return response