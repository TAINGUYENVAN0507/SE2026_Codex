from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.core.errors import APIError
from app.core.security import create_access_token, verify_password
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse, UserMeOut, UserOut
from app.schemas.common import ErrorResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Email hoặc mật khẩu không chính xác",
        },
    },
    summary="Đăng nhập người dùng",
)
def login(
    payload: LoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> LoginResponse:
    """Đăng nhập tài khoản cục bộ và trả về session cookie."""
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise APIError(
            code="INVALID_CREDENTIALS",
            message="Email hoặc mật khẩu không chính xác.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    settings = get_settings()
    token = create_access_token(user.id)
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=(settings.ENVIRONMENT == "production"),
    )
    return LoginResponse(
        user=UserOut(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
        )
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Đăng xuất người dùng",
)
def logout() -> Response:
    """Đăng xuất tài khoản và xóa session cookie."""
    settings = get_settings()
    res = Response(status_code=status.HTTP_204_NO_CONTENT)
    res.delete_cookie(
        key="session_token",
        httponly=True,
        samesite="lax",
        secure=(settings.ENVIRONMENT == "production"),
    )
    return res


@router.get(
    "/me",
    response_model=UserMeOut,
    status_code=status.HTTP_200_OK,
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Chưa đăng nhập hoặc session đã hết hạn",
        },
    },
    summary="Lấy thông tin người dùng hiện tại",
)
def get_me(current_user: CurrentUser) -> UserMeOut:
    """Trả về thông tin người dùng hiện tại từ session."""
    return UserMeOut(
        user=UserOut(
            id=current_user.id,
            email=current_user.email,
            display_name=current_user.display_name,
        )
    )
