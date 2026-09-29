from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    user_id: Optional[int] = None
    email: str


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
