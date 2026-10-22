"""Pydantic schemas cho xác thực người dùng (Auth)."""

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    """Thông tin người dùng cơ bản."""

    id: str = Field(..., description="UUID của người dùng")
    email: str = Field(..., description="Email người dùng")
    display_name: str = Field(..., description="Tên hiển thị của người dùng")

    model_config = ConfigDict(extra="forbid")


class UserMeOut(BaseModel):
    """Hợp đồng thông tin người dùng hiện tại (GET /auth/me)."""

    user: UserOut = Field(..., description="Thông tin người dùng")

    model_config = ConfigDict(extra="forbid")


class LoginRequest(BaseModel):
    """Thông tin đăng nhập."""

    email: str = Field(..., description="Email đăng nhập")
    password: str = Field(..., min_length=1, description="Mật khẩu")

    model_config = ConfigDict(extra="forbid")


class LoginResponse(BaseModel):
    """Kết quả đăng nhập thành công."""

    user: UserOut = Field(..., description="Thông tin người dùng đã đăng nhập")

    model_config = ConfigDict(extra="forbid")
