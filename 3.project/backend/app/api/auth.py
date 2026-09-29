from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..schemas.auth import (
    LoginRequest,
    LoginResponse,
    UserResponse,
    SendVerificationCodeRequest,
    SendVerificationCodeResponse,
    VerifyCodeRequest,
    VerifyCodeResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
)
from ..services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """로그인 API"""
    user = AuthService.authenticate_user(db, req.email, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )
    return LoginResponse(
        success=True,
        message="로그인 성공",
        user=UserResponse(user_id=user.user_id, email=user.email),
        token=f"mock_token_{user.user_id}",
    )


@router.post("/send-verification-code", response_model=SendVerificationCodeResponse)
@router.post("/send-code", response_model=SendVerificationCodeResponse)
def send_verification_code(req: SendVerificationCodeRequest, db: Session = Depends(get_db)):
    """이메일 인증번호 발송 API (현재 비밀번호 검증 포함)"""
    success, message, expires_in, demo_code = AuthService.send_verification_code(
        db, req.email, req.password
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    return SendVerificationCodeResponse(
        success=True,
        message=message,
        expires_in_seconds=expires_in,
        demo_code=demo_code,
    )


@router.post("/verify-code", response_model=VerifyCodeResponse)
def verify_code(req: VerifyCodeRequest, db: Session = Depends(get_db)):
    """이메일 인증번호 검증 API"""
    success, token, message = AuthService.verify_code(db, req.email, req.code)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    return VerifyCodeResponse(
        success=True,
        verification_token=token,
        message=message,
    )


@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password(req: ChangePasswordRequest, db: Session = Depends(get_db)):
    """비밀번호 변경 처리 API"""
    success, message = AuthService.change_password(
        db, req.email, req.verification_token, req.new_password
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    return ChangePasswordResponse(success=True, message=message)
