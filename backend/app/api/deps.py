"""Dependencies dùng chung cho các router của API."""

from typing import Annotated

from fastapi import Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.core.security import decode_access_token
from app.db.models.user import User
from app.db.session import get_db


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Dependency xác thực và trích xuất người dùng hiện tại từ cookie JWT session_token."""
    token = request.cookies.get("session_token")
    if not token:
        raise APIError(
            code="UNAUTHENTICATED",
            message="Chưa đăng nhập hoặc phiên làm việc đã hết hạn.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user_id = decode_access_token(token)
    if not user_id:
        raise APIError(
            code="UNAUTHENTICATED",
            message="Chưa đăng nhập hoặc phiên làm việc đã hết hạn.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise APIError(
            code="UNAUTHENTICATED",
            message="Chưa đăng nhập hoặc phiên làm việc đã hết hạn.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
