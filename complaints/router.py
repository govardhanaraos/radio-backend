from datetime import datetime
from typing import Any, Dict, List, Optional

import uuid
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, AliasChoices, ConfigDict

from auth.dependencies import verify_admin_token
from db.db import get_db

router = APIRouter()


# -----------------------------
# Pydantic models
# -----------------------------
class ComplaintModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    subject: str
    email: EmailStr
    contact: str
    description: str
    device_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("device_id", "deviceId", "deviceID"),
    )


class ComplaintReplyBody(BaseModel):
    admin_response: str = Field(..., min_length=1)


def _serialize_complaint(doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not doc:
        return {}
    out = dict(doc)
    out["_id"] = str(out["_id"])
    for key in ("created_at", "replied_at"):
        val = out.get(key)
        if val is not None and hasattr(val, "isoformat"):
            out[key] = val.isoformat()
    return out


# -----------------------------
# Public (mobile app)
# -----------------------------
@router.post("/submitcomplaint")
async def submit_complaint(data: ComplaintModel):
    try:
        db = get_db()
        if db is None:
            raise HTTPException(status_code=503, detail="Database connection failed.")

        collection = db["cust_feedback_complaints"]

        reference_no = f"GR-{uuid.uuid4().hex[:8].upper()}"

        device_id = (data.device_id or "").strip() or None

        complaint_doc: Dict[str, Any] = {
            "reference_no": reference_no,
            "name": data.name,
            "subject": data.subject,
            "email": str(data.email),
            "contact": data.contact,
            "description": data.description,
            "status": "P",
            "created_at": datetime.utcnow(),
        }
        if device_id:
            complaint_doc["device_id"] = device_id

        await collection.insert_one(complaint_doc)

        return {
            "status": "success",
            "message": "Complaint submitted successfully",
            "reference_no": reference_no,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/getcomplaint/{reference_no}")
async def get_complaint_by_reference(reference_no: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")
    collection = db["cust_feedback_complaints"]

    result = await collection.find_one({"reference_no": reference_no})

    if not result:
        raise HTTPException(status_code=404, detail="Complaint not found")

    return _serialize_complaint(result)


# -----------------------------
# Admin
# -----------------------------
@router.get(
    "/admin/complaints",
    dependencies=[Depends(verify_admin_token)],
)
async def list_complaints_admin(limit: int = 500) -> List[Dict[str, Any]]:
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")
    try:
        collection = db["cust_feedback_complaints"]
        cursor = (
            collection.find({})
            .sort("created_at", -1)
            .limit(min(max(limit, 1), 1000))
        )
        docs = await cursor.to_list(length=1000)
        return [_serialize_complaint(d) for d in docs]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch(
    "/admin/complaints/{complaint_id}",
    dependencies=[Depends(verify_admin_token)],
)
async def reply_to_complaint_admin(complaint_id: str, body: ComplaintReplyBody):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")
    try:
        oid = ObjectId(complaint_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid complaint id.")

    collection = db["cust_feedback_complaints"]
    now = datetime.utcnow()
    res = await collection.update_one(
        {"_id": oid},
        {
            "$set": {
                "admin_response": body.admin_response.strip(),
                "replied_at": now,
                "status": "R",
            }
        },
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Complaint not found.")

    updated = await collection.find_one({"_id": oid})
    return _serialize_complaint(updated)


@router.get("/serviceawake")
async def service_awake():
    return {"result": "Service awake"}
