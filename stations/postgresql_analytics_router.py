from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from db.db import get_pg_conn
import psycopg2
from psycopg2.extras import Json

router = APIRouter(
    prefix="/analytics/pg",
    tags=["PostgreSQL Analytics"],
)

class LogEntry(BaseModel):
    deviceId: str
    event: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str

@router.post("/log")
async def log_activity_pg(log: LogEntry):
    """Store user activity logs in PostgreSQL."""
    conn = get_pg_conn()
    if conn is None:
        raise HTTPException(status_code=503, detail="PostgreSQL connection failed.")
    
    try:
        cur = conn.cursor()
        # Ensure table exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_actions_logs (
                id SERIAL PRIMARY KEY,
                device_id TEXT NOT NULL,
                event TEXT NOT NULL,
                details JSONB,
                client_timestamp TEXT,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cur.execute(
            "INSERT INTO user_actions_logs (device_id, event, details, client_timestamp) VALUES (%s, %s, %s, %s)",
            (log.deviceId, log.event, Json(log.details) if log.details else None, log.timestamp)
        )
        conn.commit()
        cur.close()
        conn.close()
        return {"message": "Log stored in PostgreSQL successfully."}
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        print(f"PostgreSQL insertion error: {e}")
        raise HTTPException(status_code=500, detail=f"PostgreSQL error: {str(e)}")
