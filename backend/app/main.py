import os
from app.config import get_settings

settings = get_settings()
# Propagate LangSmith configuration into os.environ
if settings.langsmith_tracing.lower() == "true" and settings.langsmith_api_key:
    os.environ["LANGCHAIN_TRACING_V2"] = settings.langsmith_tracing
    os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    print("LangSmith tracing enabled")

print("DEBUG langsmith_tracing =", repr(settings.langsmith_tracing))
print("DEBUG langsmith_api_key =", repr(settings.langsmith_api_key[:10] + "..." if settings.langsmith_api_key else "EMPTY"))

# backend/app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import structlog
from app.dependencies import lifespan
from app.routes import auth, trips

log = structlog.get_logger()

app = FastAPI(lifespan=lifespan)

app.include_router(auth.router)
app.include_router(trips.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.exception("unhandled_exception", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )