import time
from starlette.middleware.base import BaseHTTPMiddleware

class TimerMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request, call_next):

        start = time.time()

        response = await call_next(request)

        response.headers["X-Time"] = str(time.time() - start)

        return response