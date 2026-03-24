from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from db.db import get_db
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
    db = get_db()
    users_collection = db.get_collection("admin_users")
    
    user = await users_collection.find_one({"username": form_data.username})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

@router.post("/change-password", summary="Change Admin Password")
async def change_admin_password(req: ChangePasswordRequest, username: str = Depends(verify_admin_token)):
    db = get_db()
    users_collection = db.get_collection("admin_users")
    
    user = await users_collection.find_one({"username": username})
    if not user:
        raise HTTPException(status_code=404, detail="Admin user not found")
        
    if not verify_password(req.old_password, user["password"]):
        raise HTTPException(status_code=400, detail="Incorrect original password")
        
    new_hashed_pw = get_password_hash(req.new_password)
    await users_collection.update_one(
        {"username": username},
        {"$set": {"password": new_hashed_pw}}
    )
    return {"success": True, "message": "Password changed successfully"}

async def setup_default_admin():
    db = get_db()
    users_collection = db.get_collection("admin_users")
    user_count = await users_collection.count_documents({})
    if user_count == 0:
        hashed_pw = get_password_hash("admin123")
        await users_collection.insert_one({"username": "admin", "password": hashed_pw})
        print("NOTICE: Created default admin user: admin / admin123")
