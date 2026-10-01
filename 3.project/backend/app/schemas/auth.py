from pydantic import BaseModel, Field
from typing import Optional


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    user_id: Optional[int] = None
    email: str
    role: str = "operator"
    display_name: str = ""
    must_change_password: bool = False
    deployment_mode: str = "development"


class LoginResponse(BaseModel):
    success: bool
    message: str
    user: Optional[UserResponse] = None
    token: Optional[str] = None


class SendVerificationCodeRequest(BaseModel):
    email: str
    password: str


class SendVerificationCodeResponse(BaseModel):
    success: bool
    message: str
    expires_in_seconds: int = 300
    demo_code: Optional[str] = None


class VerifyCodeRequest(BaseModel):
    email: str
    code: str


class VerifyCodeResponse(BaseModel):
    success: bool
    verification_token: Optional[str] = None
    message: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    email: str
    verification_token: str
    new_password: str


class ChangePasswordResponse(BaseModel):
    success: bool
    message: str


class SelfPasswordChange(BaseModel):
    current_password: str
    new_password: str
