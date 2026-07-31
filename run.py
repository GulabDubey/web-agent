import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    debug = os.getenv("APP_ENV", "development") == "development"

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=debug,
        workers=1 if debug else int(os.getenv("WORKERS", 4))
    )