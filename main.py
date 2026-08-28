import hashlib
import asyncio
import hmac
import os
import secrets
import smtplib
import html
import mimetypes
import uuid
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from fastapi import FastAPI, Depends, HTTPException, status, Form, UploadFile, File
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from capjs_server import CapServer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, text
from passlib.context import CryptContext
from database import get_db, engine, Base
from contextlib import asynccontextmanager

from models import User, RevokedToken, EmailVerificationCode, UserProfile, Post, Reply
from auth import create_access_token, get_current_user, verify_password, oauth2_scheme

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # create_all does not add columns to an already existing table.
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at "
            "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"
        ))
    yield

app = FastAPI(lifespan=lifespan)

FILES_DIR = Path(__file__).resolve().parent / "files"
FILES_DIR.mkdir(parents=True, exist_ok=True)
NORMAL_AVATAR = FILES_DIR / "normal.png"
if not NORMAL_AVATAR.exists():
    # A tiny valid PNG fallback; a checked-in normal.png is preferred.
    import base64
    NORMAL_AVATAR.write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    ))
app.mount("/files", StaticFiles(directory=str(FILES_DIR)), name="files")

MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_VIDEO_SIZE = 100 * 1024 * 1024
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".ogg", ".mov", ".m4v"}
IMAGE_MIME = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"}
VIDEO_MIME = {"video/mp4", "video/webm", "video/ogg", "video/quicktime", "video/x-m4v"}


class SafeHTMLParser(HTMLParser):
    allowed_tags = {
        "p", "br", "strong", "em", "u", "s", "ul", "ol", "li", "blockquote",
        "h1", "h2", "h3", "pre", "code", "a", "img", "video", "source",
    }
    allowed_attrs = {
        "a": {"href", "title", "target", "rel"},
        "img": {"src", "alt", "title", "width", "height"},
        "video": {"src", "poster", "controls", "width", "height"},
        "source": {"src", "type"},
    }
    void_tags = {"br", "img", "source"}
    skip_tags = {"script", "style", "iframe", "object", "embed", "form"}

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.output = []
        self.skip_depth = 0

    @staticmethod
    def safe_url(value: str) -> bool:
        value = value.strip()
        if not value:
            return False
        lowered = value.lower()
        return lowered.startswith(("http://", "https://", "/files/"))

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.skip_tags:
            self.skip_depth += 1
            return
        if self.skip_depth or tag not in self.allowed_tags:
            return
        clean = []
        for key, value in attrs:
            key = key.lower()
            if key.startswith("on") or key not in self.allowed_attrs.get(tag, set()):
                continue
            value = value or ""
            if key in {"href", "src", "poster"} and not self.safe_url(value):
                continue
            clean.append((key, value))
        if tag == "a":
            clean.append(("rel", "noopener noreferrer"))
            clean = [(k, v) for k, v in clean if k != "target"] + [("target", "_blank")]
        attrs_text = "".join(f' {k}="{html.escape(v, quote=True)}"' for k, v in clean)
        self.output.append(f"<{tag}{attrs_text}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.skip_tags:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif not self.skip_depth and tag in self.allowed_tags and tag not in self.void_tags:
            self.output.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.skip_depth:
            self.output.append(html.escape(data))

    def handle_entityref(self, name):
        if not self.skip_depth:
            self.output.append(f"&{name};")

    def handle_charref(self, name):
        if not self.skip_depth:
            self.output.append(f"&#{name};")

    def handle_comment(self, data):
        return


def sanitize_html(value: str) -> str:
    parser = SafeHTMLParser()
    parser.feed(value or "")
    parser.close()
    return "".join(parser.output).strip()


def avatar_url(username: str) -> str:
    return f"/files/{username}/icon.png" if (FILES_DIR / username / "icon.png").exists() else "/files/normal.png"


def user_payload(user: User, profile: UserProfile | None = None) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "bio": profile.bio if profile else "",
        "avatar_url": avatar_url(user.username),
    }

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
    post_ids = (await db.execute(select(Post.id).where(Post.author_id == current_user.id))).scalars().all()
    if post_ids:
        await db.execute(delete(Reply).where(Reply.post_id.in_(post_ids)))
        await db.execute(delete(Post).where(Post.id.in_(post_ids)))
    await db.execute(delete(Reply).where(Reply.author_id == current_user.id))
    await db.execute(delete(UserProfile).where(UserProfile.user_id == current_user.id))
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


async def _read_upload(upload: UploadFile, max_size: int) -> bytes:
    data = await upload.read(max_size + 1)
    if len(data) > max_size:
        raise HTTPException(status_code=413, detail="文件过大")
    if not data:
        raise HTTPException(status_code=400, detail="文件不能为空")
    return data


@app.post("/api/private/upload-media")
async def upload_media(
    media: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    original_ext = Path(media.filename or "").suffix.lower()
    content_type = (media.content_type or "").lower()
    username_dir = FILES_DIR / current_user.username
    username_dir.mkdir(parents=True, exist_ok=True)

    if content_type in IMAGE_MIME or original_ext in IMAGE_EXTENSIONS:
        if content_type and not content_type.startswith("image/") and original_ext not in IMAGE_EXTENSIONS:
            raise HTTPException(status_code=400, detail="不支持的图片类型")
        data = await _read_upload(media, MAX_IMAGE_SIZE)
        try:
            from PIL import Image
            from io import BytesIO
            image = Image.open(BytesIO(data))
            image.load()
            output_name = f"{uuid.uuid4().hex}.jpg"
            output_path = username_dir / output_name
            image.convert("RGB").save(output_path, "JPEG", quality=85, optimize=True)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="图片文件无效") from exc
        return {"url": f"/files/{current_user.username}/{output_name}", "type": "image"}

    if content_type in VIDEO_MIME or original_ext in VIDEO_EXTENSIONS:
        if original_ext not in VIDEO_EXTENSIONS:
            original_ext = mimetypes.guess_extension(content_type) or ".mp4"
        data = await _read_upload(media, MAX_VIDEO_SIZE)
        output_name = f"{uuid.uuid4().hex}{original_ext}"
        (username_dir / output_name).write_bytes(data)
        return {"url": f"/files/{current_user.username}/{output_name}", "type": "video"}

    raise HTTPException(status_code=400, detail="仅支持图片或视频文件")


@app.post("/api/private/upload-avatar")
async def upload_avatar(
    avatar: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if (avatar.content_type or "").lower() not in IMAGE_MIME and Path(avatar.filename or "").suffix.lower() not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="头像必须是图片")
    data = await _read_upload(avatar, MAX_IMAGE_SIZE)
    try:
        from PIL import Image
        from io import BytesIO
        image = Image.open(BytesIO(data))
        image.load()
        image = image.convert("RGBA")
        image = image.resize((256, 256), Image.Resampling.LANCZOS)
        username_dir = FILES_DIR / current_user.username
        username_dir.mkdir(parents=True, exist_ok=True)
        image.save(username_dir / "icon.png", "PNG", optimize=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="图片文件无效") from exc
    return {"avatar_url": f"/files/{current_user.username}/icon.png"}


@app.get("/api/private/profile")
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.id))
    return user_payload(current_user, result.scalar_one_or_none())


@app.patch("/api/private/profile")
async def update_profile(
    bio: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = UserProfile(user_id=current_user.id, bio=bio[:2000])
        db.add(profile)
    else:
        profile.bio = bio[:2000]
    await db.commit()
    return user_payload(current_user, profile)


@app.get("/api/users/{username}/profile")
async def get_public_profile(username: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    return user_payload(user, profile_result.scalar_one_or_none())


def _post_payload(post: Post, username: str) -> dict:
    return {
        "id": post.id,
        "title": post.title,
        "content_html": post.content_html,
        "author": username,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "updated_at": post.updated_at.isoformat() if post.updated_at else None,
    }


@app.get("/api/posts")
async def list_posts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Post, User.username).join(User, User.id == Post.author_id)
        .order_by(Post.updated_at.desc(), Post.id.desc()).limit(100)
    )
    return [_post_payload(post, username) for post, username in result.all()]


@app.post("/api/posts")
async def create_post(
    title: str = Form(...),
    content_html: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    clean_title = title.strip()[:200]
    clean_content = sanitize_html(content_html)
    if not clean_title or not clean_content:
        raise HTTPException(status_code=400, detail="标题和正文不能为空")
    post = Post(author_id=current_user.id, title=clean_title, content_html=clean_content)
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return _post_payload(post, current_user.username)


@app.get("/api/posts/{post_id}")
async def get_post(post_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Post, User.username).join(User, User.id == Post.author_id).where(Post.id == post_id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="帖子不存在")
    post, username = row
    replies_result = await db.execute(
        select(Reply, User.username).join(User, User.id == Reply.author_id)
        .where(Reply.post_id == post_id).order_by(Reply.created_at.asc(), Reply.id.asc())
    )
    replies = [
        {
            "id": reply.id,
            "content_html": reply.content_html,
            "author": reply_username,
            "created_at": reply.created_at.isoformat() if reply.created_at else None,
        }
        for reply, reply_username in replies_result.all()
    ]
    return {**_post_payload(post, username), "replies": replies}


@app.patch("/api/posts/{post_id}")
async def update_post(
    post_id: int,
    title: str = Form(...),
    content_html: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="帖子不存在")
    if post.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权编辑此帖子")
    clean_title, clean_content = title.strip()[:200], sanitize_html(content_html)
    if not clean_title or not clean_content:
        raise HTTPException(status_code=400, detail="标题和正文不能为空")
    post.title, post.content_html = clean_title, clean_content
    await db.commit()
    await db.refresh(post)
    return _post_payload(post, current_user.username)


@app.post("/api/posts/{post_id}/replies")
async def create_reply(
    post_id: int,
    content_html: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    post_result = await db.execute(select(Post.id).where(Post.id == post_id))
    if post_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="帖子不存在")
    clean_content = sanitize_html(content_html)
    if not clean_content:
        raise HTTPException(status_code=400, detail="回复内容不能为空")
    reply = Reply(post_id=post_id, author_id=current_user.id, content_html=clean_content)
    db.add(reply)
    await db.commit()
    await db.refresh(reply)
    return {
        "id": reply.id,
        "content_html": reply.content_html,
        "author": current_user.username,
        "created_at": reply.created_at.isoformat() if reply.created_at else None,
    }