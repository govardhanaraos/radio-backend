import jwt
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
import os

SECRET_KEY = os.environ.get("ADMIN_SECRET_KEY", "your-super-secret-key-123")
ALGORITHM = "HS256"

# This expects the frontend clients to send a header: Authorization: Bearer <token>
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login")

def verify_admin_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired. Please login again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
