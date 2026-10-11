import uvicorn
from app.config.settings import settings

if __name__ == "__main__":
    debug = settings.APP_ENV == "development"

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=debug,
        workers=1 if debug else settings.WORKERS
    )