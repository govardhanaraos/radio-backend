from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, AliasChoices, ConfigDict

from auth.dependencies import verify_admin_token
from db.db import get_pg_pool

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

def _generate_id():
    return uuid.uuid4().hex[:24]

def _serialize_complaint(doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not doc:
        return {}
    out = dict(doc)
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
        pool = get_pg_pool()
        if pool is None:
            raise HTTPException(status_code=503, detail="Database connection failed.")

        reference_no = f"GR-{uuid.uuid4().hex[:8].upper()}"
        device_id = (data.device_id or "").strip() or None
        new_id = _generate_id()
        now = datetime.utcnow()

        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO cust_feedback_complaints 
                (id, reference_no, name, subject, email, contact, description, status, created_at, device_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """, new_id, reference_no, data.name, data.subject, str(data.email), data.contact, data.description, "P", now, device_id)

        return {
            "status": "success",
            "message": "Complaint submitted successfully",
            "reference_no": reference_no,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/getcomplaint/{reference_no}")
async def get_complaint_by_reference(reference_no: str):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")
        
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM cust_feedback_complaints WHERE reference_no = $1", reference_no)

        if not row:
            raise HTTPException(status_code=404, detail="Complaint not found")

        return _serialize_complaint(dict(row))

# -----------------------------
# Admin
# -----------------------------
@router.get(
    "/admin/complaints",
    dependencies=[Depends(verify_admin_token)],
)
async def list_complaints_admin(limit: int = 500) -> List[Dict[str, Any]]:
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")
    try:
        actual_limit = min(max(limit, 1), 1000)
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM cust_feedback_complaints ORDER BY created_at DESC LIMIT $1", actual_limit)
            return [_serialize_complaint(dict(r)) for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.patch(
    "/admin/complaints/{complaint_id}",
    dependencies=[Depends(verify_admin_token)],
)
async def reply_to_complaint_admin(complaint_id: str, body: ComplaintReplyBody):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")
    try:
        now = datetime.utcnow()
        async with pool.acquire() as conn:
            exists = await conn.fetchval("SELECT 1 FROM cust_feedback_complaints WHERE id = $1", complaint_id)
            if not exists:
                raise HTTPException(status_code=404, detail="Complaint not found.")
                
            await conn.execute("""
                UPDATE cust_feedback_complaints 
                SET admin_response = $1, replied_at = $2, status = 'R'
                WHERE id = $3
            """, body.admin_response.strip(), now, complaint_id)
            
            updated = await conn.fetchrow("SELECT * FROM cust_feedback_complaints WHERE id = $1", complaint_id)
            return _serialize_complaint(dict(updated))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/serviceawake")
async def service_awake():
    return {"result": "Service awake"}
