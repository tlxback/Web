import hashlib
import asyncio
import hmac
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from fastapi import FastAPI, Depends, HTTPException, status, Form
from pydantic import BaseModel
from capjs_server import CapServer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from passlib.context import CryptContext
from database import get_db, engine, Base
from contextlib import asynccontextmanager

from models import User, RevokedToken, EmailVerificationCode
from auth import create_access_token, get_current_user, verify_password, oauth2_scheme

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(lifespan=lifespan)

cap = CapServer(secret_key=os.getenv("CAP_SECRET_KEY", "change-this-cap-secret"))

class CapRedeemRequest(BaseModel):
    token: str
    solutions: list

@app.post("/api/cap/challenge")
async def create_cap_challenge():
    return cap.create_challenge()

@app.post("/api/cap/redeem")
async def redeem_cap_challenge(request: CapRedeemRequest):
    result = cap.redeem(request.token, request.solutions)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail="人机验证失败")
    return result

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
VERIFICATION_CODE_EXPIRE_MINUTES = 10

def _normalize_email(email: str) -> str:
    return email.strip().lower()

def _hash_verification_code(email: str, code: str) -> str:
    secret = os.getenv("VERIFICATION_CODE_SECRET", "change-this-verification-secret")
    return hmac.new(
        secret.encode(), f"{email}:{code}".encode(), hashlib.sha256
    ).hexdigest()

def _send_verification_email(email: str, code: str, subject: str = "注册验证码") -> None:
    smtp_user = os.getenv("SMTP_USER", "tlxback@sina.com")
    smtp_password = os.getenv("SMTP_PASSWORD")
    if not smtp_user or not smtp_password:
        raise RuntimeError("SMTP_USER 和 SMTP_PASSWORD 未配置")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_user
    message["To"] = email
    message.set_content(f"你的{subject}是：{code}\n验证码有效期为 {VERIFICATION_CODE_EXPIRE_MINUTES} 分钟。")

    with smtplib.SMTP_SSL(
        os.getenv("SMTP_HOST", "smtp.sina.com"),
        int(os.getenv("SMTP_PORT", "465")),
        timeout=20,
    ) as smtp:
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)

'''app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)'''

@app.get("/")
def read_root():
    return {"message": "FastAPI 跑通了！"}

@app.get("/api/test")
def test_api():
    return {"data": "这是 Vue 发来请求后，后端返回的数据"}

'''@app.post("/api/public/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = fake_users_db.get(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    
    access_token = create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}
'''
@app.get("/api/private/users/me")
async def read_users_me(current_user = Depends(get_current_user)):
    return current_user

@app.post("/api/public/send-verification-code")
async def send_verification_code(email: str = Form(...), db: AsyncSession = Depends(get_db)):
    email = _normalize_email(email)
    existing_user = await db.execute(select(User).where(User.email == email))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    code = f"{secrets.randbelow(1_000_000):06d}"
    await db.execute(
        delete(EmailVerificationCode).where(
            EmailVerificationCode.email == email,
            EmailVerificationCode.used.is_(False),
        )
    )
    verification = EmailVerificationCode(
        email=email,
        code_hash=_hash_verification_code(email, code),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=VERIFICATION_CODE_EXPIRE_MINUTES),
    )
    db.add(verification)
    await db.commit()

    try:
        await asyncio.to_thread(_send_verification_email, email, code)
    except Exception as exc:
        await db.delete(verification)
        await db.commit()
        raise HTTPException(status_code=503, detail="验证码邮件发送失败，请稍后重试") from exc

    return {"status": True, "msg": "验证码已发送"}

@app.post("/api/public/send-login-code")
async def send_login_code(email: str = Form(...), db: AsyncSession = Depends(get_db)):
    email = _normalize_email(email)
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=400, detail="邮箱未注册")

    code = f"{secrets.randbelow(1_000_000):06d}"
    await db.execute(delete(EmailVerificationCode).where(
        EmailVerificationCode.email == email,
        EmailVerificationCode.used.is_(False),
    ))
    verification = EmailVerificationCode(
        email=email,
        code_hash=_hash_verification_code(email, code),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=VERIFICATION_CODE_EXPIRE_MINUTES),
    )
    db.add(verification)
    await db.commit()
    try:
        await asyncio.to_thread(_send_verification_email, email, code, "登录验证码")
    except Exception as exc:
        await db.delete(verification)
        await db.commit()
        raise HTTPException(status_code=503, detail="验证码邮件发送失败，请稍后重试") from exc
    return {"status": True, "msg": "登录验证码已发送"}

@app.post("/api/public/send-password-reset-code")
async def send_password_reset_code(
    email: str = Form(...),
    cap_token: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if not cap.validate(cap_token):
        raise HTTPException(status_code=400, detail="人机验证失败")

    email = _normalize_email(email)
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=400, detail="邮箱未注册")

    code = f"{secrets.randbelow(1_000_000):06d}"
    await db.execute(delete(EmailVerificationCode).where(
        EmailVerificationCode.email == email,
        EmailVerificationCode.used.is_(False),
    ))
    verification = EmailVerificationCode(
        email=email,
        code_hash=_hash_verification_code(email, code),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=VERIFICATION_CODE_EXPIRE_MINUTES),
    )
    db.add(verification)
    await db.commit()
    try:
        await asyncio.to_thread(_send_verification_email, email, code, "密码重置验证码")
    except Exception as exc:
        await db.delete(verification)
        await db.commit()
        raise HTTPException(status_code=503, detail="验证码邮件发送失败，请稍后重试") from exc
    return {"status": True, "msg": "密码重置验证码已发送"}

@app.post("/api/public/reset-password")
async def reset_password(
    email: str = Form(...),
    verification_code: str = Form(...),
    new_password: str = Form(...),
    cap_token: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if not cap.validate(cap_token):
        raise HTTPException(status_code=400, detail="人机验证失败")
    if not new_password:
        raise HTTPException(status_code=400, detail="新密码不能为空")

    email = _normalize_email(email)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="邮箱未注册")

    verification_result = await db.execute(
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.email == email,
            EmailVerificationCode.used.is_(False),
        )
        .order_by(EmailVerificationCode.created_at.desc())
    )
    verification = verification_result.scalars().first()
    if (
        verification is None
        or verification.expires_at < datetime.now(timezone.utc)
        or not hmac.compare_digest(
            verification.code_hash,
            _hash_verification_code(email, verification_code.strip()),
        )
    ):
        raise HTTPException(status_code=400, detail="验证码无效或已过期")

    verification.used = True
    if user.exist and user.hashed_token:
        db.add(RevokedToken(token_hash=user.hashed_token))
    user.exist = False
    user.hashed_token = None
    user.hashed_password = pwd_context.hash(new_password)
    await db.commit()
    return {"status": True, "msg": "密码重置成功"}

@app.post("/api/public/register")
async def register(
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(...),
    verification_code: str = Form(...),
    cap_token: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    email = _normalize_email(email)
    if not cap.validate(cap_token):
        raise HTTPException(status_code=400, detail="人机验证失败")
    existing_user = await db.execute(select(User).where(User.username == username))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    existing_email = await db.execute(select(User).where(User.email == email))
    if existing_email.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    verification_result = await db.execute(
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.email == email,
            EmailVerificationCode.used.is_(False),
        )
        .order_by(EmailVerificationCode.created_at.desc())
    )
    verification = verification_result.scalars().first()
    if (
        verification is None
        or verification.expires_at < datetime.now(timezone.utc)
        or not hmac.compare_digest(
            verification.code_hash,
            _hash_verification_code(email, verification_code.strip()),
        )
    ):
        raise HTTPException(status_code=400, detail="验证码无效或已过期")

    verification.used = True
    hashed = pwd_context.hash(password)
    new_user = User(username=username, hashed_password=hashed, email=email)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return {"status": True, "msg": "注册成功", "user_id": new_user.id}

from fastapi.responses import JSONResponse

@app.post("/api/login/code")
async def login_by_code(
    email: str = Form(...),
    verification_code: str = Form(...),
    cap_token: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if not cap.validate(cap_token):
        raise HTTPException(status_code=400, detail="人机验证失败")
    email = _normalize_email(email)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="邮箱未注册")
    verification_result = await db.execute(
        select(EmailVerificationCode)
        .where(EmailVerificationCode.email == email, EmailVerificationCode.used.is_(False))
        .order_by(EmailVerificationCode.created_at.desc())
    )
    verification = verification_result.scalars().first()
    if (verification is None or verification.expires_at < datetime.now(timezone.utc)
            or not hmac.compare_digest(
                verification.code_hash,
                _hash_verification_code(email, verification_code.strip()),
            )):
        raise HTTPException(status_code=400, detail="验证码无效或已过期")
    verification.used = True
    if user.exist and user.hashed_token:
        db.add(RevokedToken(token_hash=user.hashed_token))
    user.exist = True
    access_token = create_access_token(data={"sub": user.username})
    user.hashed_token = hashlib.sha256(access_token.encode()).hexdigest()
    await db.commit()
    response = JSONResponse(content={"access_token": access_token, "token_type": "bearer"})
    response.set_cookie(key="access_token", value=access_token, httponly=False, samesite="lax")
    return response

@app.post("/api/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), cap_token: str = Form(...), db: AsyncSession = Depends(get_db)):
    if not cap.validate(cap_token):
        raise HTTPException(status_code=400, detail="人机验证失败")
    result = await db.execute(
        select(User).where(User.username == form_data.username)
    )
    user = result.scalar_one_or_none()
    if not user or not pwd_context.verify(form_data.password, user.hashed_password): 
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"}
        )
    if user.exist: 
        revoked_entry = RevokedToken(token_hash=user.hashed_token)
        db.add(revoked_entry)
    user.exist=True
    access_token=create_access_token(data={"sub": user.username})
    user.hashed_token=hashlib.sha256(access_token.encode()).hexdigest()
    await db.commit()

    # 返回 JSON 同时在 cookie 中设置 access_token，便于前端从 cookie 读取
    resp = JSONResponse(content={"access_token": access_token, "token_type":"bearer"})
    # 为了让前端 JS 能读取 cookie（按需），这里不设置 HttpOnly；如需更安全请改为 httponly=True 并使用后端会话校验
    resp.set_cookie(key="access_token", value=access_token, httponly=False, samesite="lax")
    return resp

@app.delete("/api/private/account")
async def delete_account(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    db.add(RevokedToken(token_hash=hashlib.sha256(token.encode()).hexdigest()))
    await db.delete(current_user)
    await db.commit()

    response = JSONResponse(content={"msg": "账号已注销"})
    response.delete_cookie(key="access_token")
    return response

@app.post("/api/private/logout")
async def logout(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),  # 直接拿到当前用户
    db: AsyncSession = Depends(get_db)
):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    db.add(RevokedToken(token_hash=token_hash))
    
    current_user.exist = False
    current_user.hashed_token = None
    await db.commit()
    
    return {"msg": "登出成功"}

@app.get("/api/users")
async def get_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return users