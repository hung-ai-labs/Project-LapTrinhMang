from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.db.models import User
from app.db.session import get_session

router = APIRouter(prefix="/auth", tags=["auth"])
passwords = PasswordHash.recommended()
dummy_hash = passwords.hash("unused-timing-comparison-password")
bearer = HTTPBearer(auto_error=False)


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return str(value).lower()


class RegisterInput(LoginInput):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Họ tên không được để trống.")
        return value


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    email: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


def signing_key():
    key = get_settings().jwt_secret.get_secret_value()
    if len(key) < 32:
        raise HTTPException(503, "Chưa cấu hình JWT_SECRET đủ mạnh.")
    return key


def token_for(user):
    now = datetime.now(UTC)
    lifetime = get_settings().jwt_expire_minutes * 60
    token = jwt.encode(
        {
            "sub": user.id,
            "iat": now,
            "exp": now + timedelta(seconds=lifetime),
            "iss": "weather-stream",
            "aud": "weather-web",
            "ver": user.token_version,
            "jti": str(uuid4()),
        },
        signing_key(),
        algorithm="HS256",
    )
    return TokenOut(access_token=token, expires_in=lifetime, user=UserOut.model_validate(user))


def unauthorized():
    return HTTPException(
        401,
        "Thông tin xác thực không hợp lệ hoặc đã hết hạn.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: AsyncSession = Depends(get_session),
):
    if credentials is None:
        raise unauthorized()
    try:
        payload = jwt.decode(
            credentials.credentials,
            signing_key(),
            algorithms=["HS256"],
            issuer="weather-stream",
            audience="weather-web",
            options={"require": ["sub", "exp", "iat", "ver", "jti"]},
        )
        user = await session.get(User, payload["sub"])
        if user is None or user.token_version != payload["ver"]:
            raise unauthorized()
        return user
    except jwt.InvalidTokenError as exc:
        raise unauthorized() from exc


@router.post("/register", response_model=TokenOut, status_code=201)
async def register(
    value: RegisterInput, response: Response, session: AsyncSession = Depends(get_session)
):
    signing_key()
    user = User(
        id=str(uuid4()),
        name=value.name,
        email=str(value.email),
        password_hash=await run_in_threadpool(passwords.hash, value.password),
        token_version=0,
        created_at=datetime.now(UTC),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Email đã được sử dụng.") from exc
    response.headers["Cache-Control"] = "no-store"
    return token_for(user)


@router.post("/login", response_model=TokenOut)
async def login(
    value: LoginInput, response: Response, session: AsyncSession = Depends(get_session)
):
    signing_key()
    user = await session.scalar(select(User).where(User.email == str(value.email)))
    valid = await run_in_threadpool(
        passwords.verify, value.password, user.password_hash if user else dummy_hash
    )
    if not user or not valid:
        raise unauthorized()
    response.headers["Cache-Control"] = "no-store"
    return token_for(user)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return user


@router.post("/logout", status_code=204)
async def logout(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await session.execute(
        update(User).where(User.id == user.id).values(token_version=User.token_version + 1)
    )
    await session.commit()
