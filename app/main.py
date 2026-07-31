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

app = FastAPI(
    title = "Companiesnext Customer Support Agent",
    version = "1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1",
        "http://127.0.0.1:8000",
        "http://localhost:8000",  # if needed
        "http://127.0.0.1:5000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/widget",
    StaticFiles(directory="app/widget"),
    name="widget"
)

app.add_middleware(LoggingMiddleware)
# app.add_middleware(AuthMiddleware)
app.add_middleware(TimerMiddleware)

app.include_router(api_v1_router, prefix="/api/v1")


@app.exception_handler(AppException)
async def app_exception_handler(request, exc):
    return JSONResponse(
        status_code = exc.status_code,
        content = {
            "success": False,
            "message": exc.message,
            "errors": exc.errors
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):

    errors = {}

    for error in exc.errors():

        field = ".".join(str(x) for x in error["loc"][1:])

        errors.setdefault(field, []).append(error["msg"])

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
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