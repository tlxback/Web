import hashlib
from fastapi import FastAPI, Depends, HTTPException, status, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from passlib.context import CryptContext
from database import get_db, engine, Base
from contextlib import asynccontextmanager

from models import User, RevokedToken
from auth import create_access_token, get_current_user, verify_password, oauth2_scheme

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(lifespan=lifespan)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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

@app.post("/api/public/register")
async def register(username: str = Form(...), password: str=Form(...), email: str = Form(None), db: AsyncSession = Depends(get_db)):
    existing_user = await db.execute(select(User).where(User.username == username))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    hashed = pwd_context.hash(password)
    
    new_user = User(username=username, hashed_password=hashed, email=email)
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return {"status": True, "msg": "注册成功", "user_id": new_user.id}

@app.post("/api/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)): 
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
    return {"access_token": access_token, "token_type":"bearer"}

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