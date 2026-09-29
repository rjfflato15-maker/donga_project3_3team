import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from ..db.models import User, EmailVerification
from .email_service import EmailService


class AuthService:
    @staticmethod
    def _hash_password(password: str) -> str:
        """비밀번호 SHA-256 해시 생성"""
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        """비밀번호 검증 (평문 해시 vs 기존 해시 또는 기존 평문 호환)"""
        if plain_password == hashed_password:
            return True
        return cls._hash_password(plain_password) == hashed_password

    @classmethod
    def ensure_default_user(cls, db: Session) -> User:
        """기본 시드 계정(nj445325@gmail.com) 생성 또는 조회"""
        default_email = "nj445325@gmail.com"
        default_pw = "admin123!"

        # Check for existing admin@example.com and update to new email
        old_user = db.query(User).filter(User.email == "admin@example.com").first()
        if old_user:
            old_user.email = default_email
            db.commit()
            return old_user

        user = db.query(User).filter(User.email == default_email).first()
        if not user:
            user = User(
                email=default_email,
                password=cls._hash_password(default_pw)
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    @classmethod
    def authenticate_user(cls, db: Session, email: str, password: str) -> Optional[User]:
        """사용자 이메일 및 비밀번호 검증"""
        # Ensure initial user exists if database is fresh
        cls.ensure_default_user(db)
        
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None
        if not cls.verify_password(password, user.password):
            return None
        return user

    @classmethod
    def send_verification_code(cls, db: Session, email: str, password: str) -> Tuple[bool, str, int, Optional[str]]:
        """
        비밀번호 확인 후 6자리 이메일 인증번호 발송.
        반환: (success, message, expires_in_seconds, demo_code)
        """
        user = cls.authenticate_user(db, email, password)
        if not user:
            return False, "이메일 또는 현재 비밀번호가 일치하지 않습니다.", 0, None

        code = EmailService.generate_verification_code()
        expires_at = datetime.utcnow() + timedelta(minutes=5)

        # 기존 해당 이메일의 미완료 인증 내역 삭제/갱신
        db.query(EmailVerification).filter(EmailVerification.email == email).delete()

        verification = EmailVerification(
            email=email,
            code=code,
            expires_at=expires_at,
            is_verified=False,
            attempt_count=0,
        )
        db.add(verification)
        db.commit()

        EmailService.send_verification_email(email, code)
        return True, "인증번호가 이메일로 전송되었습니다.", 300, code

    @classmethod
    def verify_code(cls, db: Session, email: str, code: str) -> Tuple[bool, Optional[str], str]:
        """
        인증번호 검증 (유효시간 5분, 최대 시도 횟수 5회 제한).
        성공 시 1회성 verification_token 반환.
        반환: (success, verification_token, message)
        """
        record = (
            db.query(EmailVerification)
            .filter(EmailVerification.email == email)
            .order_by(EmailVerification.created_at.desc())
            .first()
        )

        if not record:
            return False, None, "발송된 인증번호가 없습니다. 인증번호를 먼저 요청하세요."

        if record.attempt_count >= 5:
            return False, None, "인증 시도 횟수(5회)를 초과했습니다. 인증번호를 재발송해주세요."

        record.attempt_count += 1
        db.commit()

        if datetime.utcnow() > record.expires_at:
            return False, None, "인증번호가 만료되었습니다. (유효시간 5분)"

        if record.code != code.strip():
            remaining = 5 - record.attempt_count
            return False, None, f"인증번호가 일치하지 않습니다. (남은 시도 횟수: {remaining}회)"

        # 인증 성공 -> token 발급
        token = f"verif_token_{uuid.uuid4().hex}"
        record.is_verified = True
        record.verification_token = token
        db.commit()

        return True, token, "인증에 성공하였습니다."

    @classmethod
    def change_password(
        cls, db: Session, email: str, verification_token: str, new_password: str
    ) -> Tuple[bool, str]:
        """
        인증 토큰 검증 후 신규 비밀번호 변경
        """
        record = (
            db.query(EmailVerification)
            .filter(
                EmailVerification.email == email,
                EmailVerification.verification_token == verification_token,
                EmailVerification.is_verified == True,
            )
            .first()
        )

        if not record:
            return False, "유효하지 않거나 만료된 인증 토큰입니다."

        user = db.query(User).filter(User.email == email).first()
        if not user:
            return False, "해당 이메일의 사용자를 찾을 수 없습니다."

        # 비밀번호 변경
        user.password = cls._hash_password(new_password)
        # 사용 완료된 인증 레코드 삭제
        db.delete(record)
        db.commit()

        return True, "비밀번호가 성공적으로 변경되었습니다."
