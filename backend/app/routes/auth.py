# backend/app/routes/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import bcrypt
from jose import jwt
import datetime
from app.models.db import User
from app.models.schemas import UserCreate, LoginRequest, Token, CurrentUser
from app.config import get_settings
from app.dependencies import get_session

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, session: AsyncSession = Depends(get_session)):
    stmt = select(User).where(User.email == user_in.email)
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = hash_password(user_in.password)
    user = User(email=user_in.email, hashed_password=hashed)
    session.add(user)
    await session.commit()
    return {"msg": "User created"}


@router.post("/token", response_model=Token)
async def login(login_in: LoginRequest, session: AsyncSession = Depends(get_session)):
    stmt = select(User).where(User.email == login_in.email)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_in.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user.id), "exp": expire}
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return Token(access_token=token, token_type="bearer")