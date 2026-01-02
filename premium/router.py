import base64
import json
import uuid
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.db import get_db, SECRET_KEY, FIXED_IV

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
        print(f"jsondecrypted: {json.loads(decrypted.decode("utf-8"))}")
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
    db = get_db()
    plain_key = uuid.uuid4().hex[:6].upper()
    encrypted_license = encrypt_license(plain_key)

    new_user_doc = {
        "plain_key": plain_key,  # For admin reference
        "license_key": encrypted_license,  # The actual key used for validation
        "active_devices": [],
        "created_at": datetime.utcnow()
    }

    await db["premium_users"].insert_one(new_user_doc)

    return {
        "status": "success",
        "plain_key_for_admin": plain_key,
        "encrypted_license": encrypted_license
    }


@router.post("/verify-license")
async def verify_license(request: EncryptedRequest):
    """Validates the encrypted key directly against the DB."""
    data = decrypt_payload(request.payload)
    # 'data' now contains 'license_key' (already encrypted by Flutter) and 'device_id'
    print(f"{data['device_id']} | {data['license_key']}")

    db = get_db()
    premium_col = db["premium_users"]
    logs_col = db["logs"]

    # Search using the encrypted license string
    user = await premium_col.find_one({"license_key": data["license_key"]})

    if not user:
        await logs_col.insert_one({
            "deviceId": data["device_id"],
            "event": "License verification failed: Encrypted key mismatch",
            "timestamp": datetime.utcnow().isoformat()
        })
        raise HTTPException(status_code=404, detail="License key not found.")

    active_devices = user.get("active_devices", [])
    print(f"active_devices: {active_devices}")

    if data["device_id"] in active_devices or len(active_devices) < 3:
        if data["device_id"] not in active_devices:
            active_devices.append(data["device_id"])
            await premium_col.update_one(
                {"license_key": data["license_key"]},
                {"$set": {"active_devices": active_devices}}
            )

        await logs_col.insert_one({
            "deviceId": data["device_id"],
            "event": "Global ads enabled: false",
            "details": {"action": "verified"},
            "timestamp": datetime.utcnow().isoformat()
        })
        return {"status": "success", "is_premium": True}

    raise HTTPException(status_code=403, detail="Device limit reached.")

@router.post("/list-devices")
async def list_devices(request: EncryptedRequest):
    """Accepts encrypted request to list devices for that specific encrypted key."""
    data = decrypt_payload(request.payload)
    db = get_db()
    user = await db["premium_users"].find_one({"license_key": data["license_key"]})

    if not user:
        raise HTTPException(status_code=404, detail="License not found.")
    return {"active_devices": user.get("active_devices", [])}

@router.post("/remove-device")
async def remove_device(request: EncryptedRequest):
    """Removes a device using the encrypted license key for lookups."""
    data = decrypt_payload(request.payload)
    db = get_db()

    await db["premium_users"].update_one(
        {"license_key": data["license_key"]},
        {"$pull": {"active_devices": data["device_id"]}}
    )

    await db["logs"].insert_one({
        "deviceId": data["device_id"],
        "event": "Device unlinked",
        "timestamp": datetime.utcnow().isoformat()
    })
    return {"status": "success", "message": "Device removed"}