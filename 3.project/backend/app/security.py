import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from .config import ALLOWED_ORIGINS, COOKIE_SECURE, SESSION_HOURS, DEPLOYMENT_MODE
from .db.database import get_db
from .db.models import User, UserProfile, AuthSession

COOKIE_NAME = "contract_session"
PASSWORD_ITERATIONS = 600_000
MAX_PASSWORD_ITERATIONS = 2_000_000
_PASSWORD_RECORD = re.compile(r"pbkdf2_sha256\$([1-9][0-9]{5,6})\$([0-9a-f]{32})\$([0-9a-f]{64})")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PASSWORD_ITERATIONS).hex()
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    # Legacy/plaintext records require an explicit account reset; never accept a
    # stored password/hash string as the submitted password.
    if not isinstance(password, str) or not 1 <= len(password) <= 128 or not isinstance(stored, str):
        return False
    record = _PASSWORD_RECORD.fullmatch(stored)
    if not record:
        return False
    rounds_text, salt, expected = record.groups()
    rounds = int(rounds_text)
    # Validate before hashing: malformed DB records must not request unlimited
    # CPU work or weaken the configured password hashing cost.
    if not PASSWORD_ITERATIONS <= rounds <= MAX_PASSWORD_ITERATIONS:
        return False
    try:
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), rounds).hex()
    except (ValueError, TypeError, UnicodeError, OverflowError):
        return False
    return hmac.compare_digest(actual, expected)


def validate_password(password: str):
    if len(password) < 12 or len(password) > 128:
        raise HTTPException(400, "비밀번호는 12자 이상 128자 이하로 입력하세요.")


@dataclass
class Actor:
    user_id: int
    email: str
    role: str
    display_name: str
    must_change_password: bool
    deployment_mode: str = DEPLOYMENT_MODE


def actor_for(user: User, profile: UserProfile) -> Actor:
    return Actor(user.user_id, user.email, profile.role, profile.display_name, profile.must_change_password)


def token_from(request: Request) -> str:
    header = request.headers.get("authorization", "")
    return header[7:] if header.startswith("Bearer ") else request.cookies.get(COOKIE_NAME, "")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Actor:
    token = token_from(request)
    session = db.get(AuthSession, hashlib.sha256(token.encode()).hexdigest()) if token else None
    if not session or session.expires_at <= datetime.utcnow():
        raise HTTPException(401, "로그인 시간이 만료되었습니다. 다시 로그인하세요.")
    user = db.get(User, session.user_id)
    profile = db.get(UserProfile, session.user_id)
    if not user or not profile or not profile.active:
        raise HTTPException(401, "사용할 수 없는 계정입니다.")
    actor = actor_for(user, profile)
    request.state.actor = actor
    if request.method not in {"GET", "HEAD", "OPTIONS"} and not request.headers.get("authorization"):
        origin = request.headers.get("origin")
        if origin and origin not in ALLOWED_ORIGINS:
            origin_parts = urlsplit(origin)
            if origin_parts.netloc != request.headers.get("host") or origin_parts.scheme != request.url.scheme:
                raise HTTPException(403, "허용되지 않은 접속 주소입니다.")
    return actor


def authorize_company_request(request: Request, actor: Actor = Depends(get_current_user), db: Session = Depends(get_db)):
    if actor.must_change_password:
        raise HTTPException(403, "먼저 초기 비밀번호를 변경하세요.")
    if actor.role not in {"operator", "representative", "admin"}:
        raise HTTPException(403, "등록된 업무 권한이 없습니다.")
    if actor.role == "representative" and request.method not in {"GET", "HEAD", "OPTIONS"}:
        path = request.url.path
        allowed = path.endswith("/reviews") or path.endswith("/validate") or path.endswith("/simulate") or path.startswith("/api/pilot/")
        if not allowed:
            raise HTTPException(403, "대표 계정은 자료를 조회하고 최종 확인합니다. 자료 등록·수정은 담당자에게 요청하세요.")
    from .db.models import ContractExclusion, Document
    path = request.url.path
    match = re.match(r'/api/(?:pilot/)?contracts/(\d+)(?:/|$)', path)
    cid = int(match[1]) if match else None
    document_match = re.match(r'/api/documents/(\d+)(?:/|$)', path)
    if document_match:
        document = db.get(Document, int(document_match[1]))
        cid = document.contract_id if document else None
    if cid and db.get(ContractExclusion, cid) and not path.endswith('/restore'):
        raise HTTPException(404, '제외한 계약입니다. 계약 찾기에서 복원하세요.')
    return actor


def require_operator(actor: Actor = Depends(get_current_user)) -> Actor:
    if actor.role not in {"operator", "admin"}:
        raise HTTPException(403, "담당자 권한이 필요합니다.")
    return actor


def require_representative(actor: Actor = Depends(get_current_user)) -> Actor:
    if actor.role not in {"representative", "admin"}:
        raise HTTPException(403, "대표 권한이 필요합니다.")
    return actor


def create_session(db: Session, user_id: int, response: Response) -> str:
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user_id,
                       expires_at=datetime.utcnow() + timedelta(hours=SESSION_HOURS)))
    db.commit()
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=COOKIE_SECURE, samesite="lax",
                        max_age=SESSION_HOURS * 3600, path="/")
    return token
