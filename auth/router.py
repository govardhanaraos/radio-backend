from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from db.db import get_pg_pool
from pydantic import BaseModel
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
import os

from .dependencies import SECRET_KEY, ALGORITHM, verify_admin_token

router = APIRouter(prefix="/admin", tags=["Admin Auth"])

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days validity for admin

def verify_password(plain_password: str, hashed_password: str):
    if isinstance(hashed_password, str):
        hashed_password_bytes = hashed_password.encode('utf-8')
    else:
        hashed_password_bytes = hashed_password
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password_bytes)

def get_password_hash(password: str):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
        
    async with pool.acquire() as conn:
        user_row = await conn.fetchrow("SELECT username, password FROM admin_users WHERE username = $1", form_data.username)
    
    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not verify_password(form_data.password, user_row["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(data={"sub": user_row["username"]})
    return {"access_token": access_token, "token_type": "bearer"}

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

@router.post("/change-password", summary="Change Admin Password")
async def change_admin_password(req: ChangePasswordRequest, username: str = Depends(verify_admin_token)):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
        
    async with pool.acquire() as conn:
        user_row = await conn.fetchrow("SELECT username, password FROM admin_users WHERE username = $1", username)
        
        if not user_row:
            raise HTTPException(status_code=404, detail="Admin user not found")
            
        if not verify_password(req.old_password, user_row["password"]):
            raise HTTPException(status_code=400, detail="Incorrect original password")
            
        new_hashed_pw = get_password_hash(req.new_password)
        await conn.execute("UPDATE admin_users SET password = $1 WHERE username = $2", new_hashed_pw, username)
        
    return {"success": True, "message": "Password changed successfully"}

async def setup_default_admin():
    pool = get_pg_pool()
    if pool is None:
        print("PG pool not connected. Cannot setup default admin.")
        return
        
    async with pool.acquire() as conn:
        user_count = await conn.fetchval("SELECT COUNT(*) FROM admin_users")
        if user_count == 0:
            hashed_pw = get_password_hash("admin123")
            await conn.execute("INSERT INTO admin_users (username, password) VALUES ($1, $2)", "admin", hashed_pw)
            print("NOTICE: Created default admin user: admin / admin123")
