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