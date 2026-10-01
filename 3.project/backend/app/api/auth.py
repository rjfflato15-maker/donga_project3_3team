import hashlib
import threading
import time
from collections import defaultdict, deque
from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..db.models import User, UserProfile, AuthSession
from ..schemas.auth import LoginRequest, LoginResponse, UserResponse, SelfPasswordChange
from ..security import (Actor, actor_for, get_current_user, hash_password, verify_password,
                        validate_password, create_session, token_from, COOKIE_NAME)

router = APIRouter(prefix="/api/auth", tags=["Auth"])
_attempts = defaultdict(deque)
_lock = threading.Lock()


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    key = ((request.client.host if request.client else "local"), req.email.strip().lower())
    now = time.monotonic()
    with _lock:
        recent = _attempts[key]
        while recent and recent[0] < now - 300:
            recent.popleft()
        if len(recent) >= 8:
            raise HTTPException(429, "로그인 시도가 많습니다. 5분 후 다시 시도하세요.")
        recent.append(now)
    user = db.query(User).filter(User.email == req.email.strip().lower()).first()
    if not user or not verify_password(req.password, user.password):
        raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다.")
    profile = db.get(UserProfile, user.user_id)
    if not profile or not profile.active:
        raise HTTPException(403, "대표에게 계정 등록을 요청하세요.")
    create_session(db, user.user_id, response)
    with _lock:
        _attempts.pop(key, None)
    return LoginResponse(success=True, message="로그인 성공", user=UserResponse(**asdict(actor_for(user, profile))))


@router.get("/me", response_model=UserResponse)
def me(actor: Actor = Depends(get_current_user)):
    return UserResponse(**asdict(actor))


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = token_from(request)
    if token:
        db.query(AuthSession).filter(AuthSession.token_hash == hashlib.sha256(token.encode()).hexdigest()).delete()
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"success": True}


@router.post("/password", response_model=UserResponse)
def change_own_password(req: SelfPasswordChange, response: Response, db: Session = Depends(get_db),
                        actor: Actor = Depends(get_current_user)):
    user = db.get(User, actor.user_id)
    if not verify_password(req.current_password, user.password):
        raise HTTPException(400, "현재 비밀번호가 올바르지 않습니다.")
    validate_password(req.new_password)
    if req.new_password == req.current_password:
        raise HTTPException(400, "새 비밀번호를 다르게 설정하세요.")
    user.password = hash_password(req.new_password)
    profile = db.get(UserProfile, actor.user_id)
    profile.must_change_password = False
    db.query(AuthSession).filter(AuthSession.user_id == actor.user_id).delete()
    create_session(db, actor.user_id, response)
    return UserResponse(**asdict(actor_for(user, profile)))


@router.post("/send-verification-code")
@router.post("/send-code")
@router.post("/verify-code")
@router.post("/change-password")
def retired_email_reset():
    raise HTTPException(410, "사내망에서는 로그인 후 비밀번호를 변경하거나 대표에게 초기화를 요청하세요.")
