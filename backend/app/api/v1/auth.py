"""Router cho xác thực người dùng (Auth)."""

import json
from pathlib import Path

from fastapi import APIRouter, Response, status

from app.core.errors import APIError
from app.schemas.auth import LoginRequest, LoginResponse, UserMeOut
from app.schemas.common import ErrorResponse

router = APIRouter(prefix="/auth", tags=["Auth"])

FIXTURE_PATH = (
    Path(__file__).resolve().parents[4] / "contracts" / "fixtures" / "api" / "user_me.json"
)


def load_user_me_fixture() -> dict:
    """Đọc dữ liệu fixture thông tin người dùng hiện tại."""
    if FIXTURE_PATH.is_file():
        with open(FIXTURE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {
        "user": {
            "id": "u-03a1b2c3-d4e5-4f6a-8b9c-0d1e2f3a4b5c",
            "email": "user@example.com",
            "display_name": "Nguyễn Văn A",
        }
    }


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
def login(payload: LoginRequest, response: Response) -> LoginResponse:
    """Đăng nhập tài khoản cục bộ và trả về session cookie."""
    if payload.email == "invalid@example.com" or payload.password == "wrong-password":
        raise APIError(
            code="INVALID_CREDENTIALS",
            message="Email hoặc mật khẩu không chính xác.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    data = load_user_me_fixture()
    response.set_cookie(
        key="session_token",
        value="mock-session-token-v0",
        httponly=True,
        samesite="lax",
    )
    return LoginResponse(user=data["user"])


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Đăng xuất người dùng",
)
def logout(response: Response) -> Response:
    """Đăng xuất tài khoản và xóa session cookie."""
    response.delete_cookie(key="session_token")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
def get_me() -> UserMeOut:
    """Trả về thông tin người dùng hiện tại từ session."""
    data = load_user_me_fixture()
    return UserMeOut.model_validate(data)
