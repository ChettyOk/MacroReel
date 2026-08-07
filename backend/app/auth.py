"""JWT auth, password hashing, and Google OAuth verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models import User
from app.schemas import (
    AuthResponse,
    ForgotPasswordLookup,
    ForgotPasswordQuestion,
    ForgotPasswordReset,
    GoogleAuthRequest,
    OkResponse,
    SecurityQuestionUpdate,
    UserLogin,
    UserRead,
    UserRegister,
)

bearer_scheme = HTTPBearer(auto_error=False)
router = APIRouter(prefix="/auth", tags=["auth"])


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _normalize_security_answer(answer: str) -> str:
    return answer.strip().lower()


def hash_security_answer(answer: str) -> str:
    return hash_password(_normalize_security_answer(answer))


def verify_security_answer(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    return verify_password(_normalize_security_answer(plain), hashed)


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return int(sub)
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from e


def user_to_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        name=user.name,
        picture_url=user.picture_url,
        has_password=bool(user.password_hash),
        has_security_question=bool(user.security_question and user.security_answer_hash),
        created_at=user.created_at,
    )


def _issue_auth_response(user: User) -> AuthResponse:
    return AuthResponse(access_token=create_access_token(user.id), user=user_to_read(user))


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = decode_access_token(credentials.credentials)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    try:
        user_id = decode_access_token(credentials.credentials)
    except HTTPException:
        return None
    return db.get(User, user_id)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _user_for_password_recovery(db: Session, email: str) -> User:
    user = db.scalars(select(User).where(User.email == email)).first()
    if (
        user is None
        or not user.password_hash
        or not user.security_question
        or not user.security_answer_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Password recovery is not available for this account",
        )
    return user


def _upsert_google_user(db: Session, *, sub: str, email: str, name: str | None, picture: str | None) -> User:
    user = db.scalars(select(User).where(User.google_sub == sub)).first()
    if user is None:
        user = db.scalars(select(User).where(User.email == email)).first()
    if user is None:
        user = User(
            email=email,
            google_sub=sub,
            name=name,
            picture_url=picture,
        )
        db.add(user)
    else:
        user.google_sub = sub
        user.email = email
        if name:
            user.name = name
        if picture:
            user.picture_url = picture
        user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(body: UserRegister, db: Annotated[Session, Depends(get_db)]) -> AuthResponse:
    email = _normalize_email(body.email)
    existing = db.scalars(select(User).where(User.email == email)).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        name=body.name.strip() if body.name else None,
        security_question=body.security_question,
        security_answer_hash=hash_security_answer(body.security_answer),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_auth_response(user)


@router.post("/login", response_model=AuthResponse)
def login(body: UserLogin, db: Annotated[Session, Depends(get_db)]) -> AuthResponse:
    email = _normalize_email(body.email)
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return _issue_auth_response(user)


@router.post("/google", response_model=AuthResponse)
def google_auth(body: GoogleAuthRequest, db: Annotated[Session, Depends(get_db)]) -> AuthResponse:
    if not config.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in isn’t available right now. Use email and password instead.",
        )
    try:
        idinfo = google_id_token.verify_oauth2_token(
            body.id_token,
            google_requests.Request(),
            config.GOOGLE_CLIENT_ID,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token") from e

    sub = idinfo.get("sub")
    email = idinfo.get("email")
    if not sub or not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google account missing email")

    user = _upsert_google_user(
        db,
        sub=sub,
        email=_normalize_email(email),
        name=idinfo.get("name"),
        picture=idinfo.get("picture"),
    )
    return _issue_auth_response(user)


@router.get("/me", response_model=UserRead)
def me(user: Annotated[User, Depends(get_current_user)]) -> UserRead:
    return user_to_read(user)


@router.post("/forgot-password/lookup", response_model=ForgotPasswordQuestion)
def forgot_password_lookup(body: ForgotPasswordLookup, db: Annotated[Session, Depends(get_db)]) -> ForgotPasswordQuestion:
    user = _user_for_password_recovery(db, _normalize_email(body.email))
    return ForgotPasswordQuestion(security_question=user.security_question or "")


@router.post("/forgot-password/reset", response_model=OkResponse)
def forgot_password_reset(body: ForgotPasswordReset, db: Annotated[Session, Depends(get_db)]) -> OkResponse:
    user = _user_for_password_recovery(db, _normalize_email(body.email))
    if not verify_security_answer(body.security_answer, user.security_answer_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect security answer")
    user.password_hash = hash_password(body.new_password)
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    return OkResponse()


@router.put("/security-question", response_model=OkResponse)
def update_security_question(
    body: SecurityQuestionUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OkResponse:
    if not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set a password on your account before adding a security question",
        )
    if user.password_hash and not body.current_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is required")
    if not verify_password(body.current_password or "", user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")
    user.security_question = body.security_question
    user.security_answer_hash = hash_security_answer(body.security_answer)
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    return OkResponse()
