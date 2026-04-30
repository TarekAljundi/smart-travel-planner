# backend/app/dependencies.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from openai import AsyncOpenAI
from sentence_transformers import SentenceTransformer
import joblib
import structlog
from app.config import get_settings
from app.models.schemas import CurrentUser
from typing import AsyncGenerator

settings = get_settings()
log = structlog.get_logger()


# ---------- Lifespan ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log.info("app.startup")
    app.state.engine = create_async_engine(settings.database_url, echo=False)
    app.state.async_session_factory = async_sessionmaker(
        app.state.engine, class_=AsyncSession, expire_on_commit=False
    )
    app.state.llm = AsyncOpenAI(
        api_key=settings.groq_api_key,
        base_url=settings.groq_api_base,
    )
    app.state.embedder = SentenceTransformer(settings.embedding_model)

    try:
        app.state.classifier = joblib.load(settings.ml_model_path)
        log.info("ml.model.loaded")
    except FileNotFoundError:
        log.warning("ml.model.not_found", path=settings.ml_model_path)
        app.state.classifier = None

    yield

    # Shutdown
    try:
        await app.state.engine.dispose()
    except Exception:
        pass   # connection may already be closed – safe to ignore
    log.info("app.shutdown")


# ---------- Dependencies ----------
async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.async_session_factory() as session:
        yield session


def get_llm(request: Request) -> AsyncOpenAI:
    return request.app.state.llm


def get_embedder(request: Request) -> SentenceTransformer:
    return request.app.state.embedder


def get_classifier(request: Request):
    if request.app.state.classifier is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML model not loaded",
        )
    return request.app.state.classifier


# ---------- Auth ----------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    try:
        from jose import jwt, JWTError
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return CurrentUser(id=int(user_id))
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def verify_token_manually(token: str, engine) -> bool | int:
    """Used for SSE where custom headers aren't possible."""
    try:
        from jose import jwt, JWTError
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        user_id: int = payload.get("sub")
        return int(user_id) if user_id else False
    except JWTError:
        return False