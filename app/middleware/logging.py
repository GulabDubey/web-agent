import time

from starlette.middleware.base import BaseHTTPMiddleware

class LoggingMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request, call_next):

        print(f"{request.method} {request.url}")

        start = time.time()

        response = await call_next(request)

        end = time.time()

        print(f"Completed in {end-start:.2f}s")

        return response
