from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from datetime import datetime
from db.db import get_db
import uuid

router = APIRouter()

# -----------------------------
# Pydantic Model for Validation
# -----------------------------
class ComplaintModel(BaseModel):
    name: str
    subject: str
    email: EmailStr
    contact: str
    description: str


# -----------------------------
# POST /submitcomplaint
# -----------------------------
@router.post("/submitcomplaint")
async def submit_complaint(data: ComplaintModel):
    try:
        db = get_db()
        if db is None:
            raise HTTPException(status_code=503, detail="Database connection failed.")

        collection = db["cust_feedback_complaints"]

        # Generate unique complaint reference number
        reference_no = f"GR-{uuid.uuid4().hex[:8].upper()}"

        complaint_doc = {
            "reference_no": reference_no,
            "name": data.name,
            "subject": data.subject,
            "email": data.email,
            "contact": data.contact,
            "description": data.description,
            "status": "P",  # NEW FIELD
            "created_at": datetime.utcnow()
        }

        await collection.insert_one(complaint_doc)

        return {
            "status": "success",
            "message": "Complaint submitted successfully",
            "reference_no": reference_no
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/getcomplaint/{reference_no}")
async def get_complaint(reference_no: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")
    collection = db["cust_feedback_complaints"]

    result = await collection.find_one({"reference_no": reference_no})

    if not result:
        raise HTTPException(status_code=404, detail="Complaint not found")

    result["_id"] = str(result["_id"])
    result["created_at"] = result["created_at"].isoformat()

    return result