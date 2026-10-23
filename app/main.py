from fastapi import FastAPI
from app.core.exceptions import AppException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api.v1.routes import router as api_v1_router
from app.middleware.auth import AuthMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.timer import TimerMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.services.llm_config_service import llm_config_service
from app.services.question_limit_service import question_limit_service
from app.services.subscription_service import subscription_service

app = FastAPI(
    title = "Companiesnext Customer Support Agent",
    version = "1.0.0"
)

class WidgetCORSMiddleware:
    """
    CORS only for the browser-facing widget endpoints. Any customer site may
    call them cross-origin; authorization comes from the site key, widget
    token and Django verification, never from CORS. Other endpoints are
    server-to-server and get no CORS headers.
    """

    PATHS = ("/widget/", "/api/v1/widget/", "/api/v1/chat", "/api/v1/contact-us")

    def __init__(self, app):
        self.app = app
        self.cors = CORSMiddleware(
            app,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
            expose_headers=["Retry-After"],
            max_age=600,
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith(self.PATHS):
            await self.cors(scope, receive, send)
        else:
            await self.app(scope, receive, send)


app.add_middleware(WidgetCORSMiddleware)


class WidgetStaticFiles(StaticFiles):
    # Make browsers revalidate (cheap 304 via ETag) so host sites always
    # pick up the latest widget instead of a stale cached copy.
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


app.mount(
    "/widget",
    WidgetStaticFiles(directory="app/widget"),
    name="widget"
)

app.add_middleware(LoggingMiddleware)
# app.add_middleware(AuthMiddleware)
app.add_middleware(TimerMiddleware)

app.include_router(api_v1_router, prefix="/api/v1")


@app.on_event("shutdown")
async def close_http_clients():
    await subscription_service.aclose()
    await llm_config_service.aclose()
    await question_limit_service.aclose()


@app.exception_handler(AppException)
async def app_exception_handler(request, exc):
    content = {
        "success": False,
        "message": exc.message,
        "errors": exc.errors
    }
    if exc.code:
        content["code"] = exc.code

    return JSONResponse(
        status_code = exc.status_code,
        content = content,
        headers = exc.headers
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):

    errors = {}

    for error in exc.errors():

        field = ".".join(str(x) for x in error["loc"][1:])

        errors.setdefault(field, []).append(error["msg"])

    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "code": "invalid_request",
            "message": "Validation Error",
            "errors": errors
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal Server Error"
        }
    )

@app.get("/")
async def root():
    return {
        "status": "success",
        "message": "Agent is running..."
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }