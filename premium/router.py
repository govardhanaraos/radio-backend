import base64
import json
import uuid
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.db import get_pg_pool, SECRET_KEY, FIXED_IV
import json as py_json

router = APIRouter()


# --- Security Helpers ---

def encrypt_license(plain_key: str):
    """Encrypts the 6-digit key for database storage and client delivery."""
    raw_bytes = plain_key.encode("utf-8")
    cipher = AES.new(SECRET_KEY, AES.MODE_CBC, FIXED_IV)
    encrypted_bytes = cipher.encrypt(pad(raw_bytes, AES.block_size))
    return base64.b64encode(encrypted_bytes).decode("utf-8")


def decrypt_payload(encrypted_text: str):
    """Decrypts the full request payload containing device info and encrypted key."""
    try:
        cipher = AES.new(SECRET_KEY, AES.MODE_CBC, FIXED_IV)
        print(f"ciphertext: {encrypted_text},cipher: {cipher}")
        decrypted = unpad(cipher.decrypt(base64.b64decode(encrypted_text)), AES.block_size)
        print(f"decrypted: {decrypted}")
        print(f"jsondecrypted: {json.loads(decrypted.decode('utf-8'))}")
        return json.loads(decrypted.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Data decryption failed.")


# --- Models ---

class EncryptedRequest(BaseModel):
    payload: str  # Encrypted JSON containing 'license_key' (encrypted) and 'device_id'


# --- Endpoints ---

@router.post("/generate-key")
async def generate_key():
    """Generates a key, encrypts it, and stores both versions in DB."""
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
        
    plain_key = uuid.uuid4().hex[:6].upper()
    encrypted_license = encrypt_license(plain_key)
    new_id = uuid.uuid4().hex[:24]

    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO premium_users (id, plain_key, license_key, active_devices, created_at)
            VALUES ($1, $2, $3, $4, $5)
        """, new_id, plain_key, encrypted_license, py_json.dumps([]), datetime.utcnow())

    return {
        "status": "success",
        "plain_key_for_admin": plain_key,
        "encrypted_license": encrypted_license
    }


@router.post("/verify-license")
async def verify_license(request: EncryptedRequest):
    """Validates the encrypted key directly against the DB."""
    data = decrypt_payload(request.payload)
    print(f"{data.get('device_id')} | {data.get('license_key')}")

    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")

    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT active_devices FROM premium_users WHERE license_key = $1", data["license_key"])

        if not user:
            await conn.execute("""
                INSERT INTO user_actions_logs (device_id, event, client_timestamp)
                VALUES ($1, $2, $3)
            """, data["device_id"], "License verification failed: Encrypted key mismatch", datetime.utcnow().isoformat())
            raise HTTPException(status_code=404, detail="License key not found.")

        # In PostgreSQL, active_devices is JSONB string
        active_devices_str = user["active_devices"]
        active_devices = py_json.loads(active_devices_str) if isinstance(active_devices_str, str) else (active_devices_str or [])
        print(f"active_devices: {active_devices}")

        if data["device_id"] in active_devices or len(active_devices) < 3:
            if data["device_id"] not in active_devices:
                active_devices.append(data["device_id"])
                await conn.execute("""
                    UPDATE premium_users SET active_devices = $1 WHERE license_key = $2
                """, py_json.dumps(active_devices), data["license_key"])

            details = py_json.dumps({"action": "verified"})
            await conn.execute("""
                INSERT INTO user_actions_logs (device_id, event, details, client_timestamp)
                VALUES ($1, $2, $3, $4)
            """, data["device_id"], "Global ads enabled: false", details, datetime.utcnow().isoformat())
            return {"status": "success", "is_premium": True}

    raise HTTPException(status_code=403, detail="Device limit reached.")

@router.post("/list-devices")
async def list_devices(request: EncryptedRequest):
    """Accepts encrypted request to list devices for that specific encrypted key."""
    data = decrypt_payload(request.payload)
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
        
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT active_devices FROM premium_users WHERE license_key = $1", data["license_key"])

        if not user:
            raise HTTPException(status_code=404, detail="License not found.")
            
        active_devices_str = user["active_devices"]
        active_devices = py_json.loads(active_devices_str) if isinstance(active_devices_str, str) else (active_devices_str or [])
        return {"active_devices": active_devices}

@router.post("/remove-device")
async def remove_device(request: EncryptedRequest):
    """Removes a device using the encrypted license key for lookups."""
    data = decrypt_payload(request.payload)
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")

    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT active_devices FROM premium_users WHERE license_key = $1", data["license_key"])
        if user:
            active_devices_str = user["active_devices"]
            active_devices = py_json.loads(active_devices_str) if isinstance(active_devices_str, str) else (active_devices_str or [])
            if data["device_id"] in active_devices:
                active_devices.remove(data["device_id"])
                await conn.execute("UPDATE premium_users SET active_devices = $1 WHERE license_key = $2", py_json.dumps(active_devices), data["license_key"])

        await conn.execute("""
            INSERT INTO user_actions_logs (device_id, event, client_timestamp)
            VALUES ($1, $2, $3)
        """, data["device_id"], "Device unlinked", datetime.utcnow().isoformat())
        
    return {"status": "success", "message": "Device removed"}