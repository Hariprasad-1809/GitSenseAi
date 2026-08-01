import uuid
import logging
import time
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, status
from app.db.supabase import get_db_connection
from app.config import settings
from app.models.schemas import SessionResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions", tags=["Sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def start_session():
    """
    Creates a new temporary anonymous session.
    Logs precise stage execution times for performance tracking.
    """
    t_start = time.perf_counter()
    logger.info("Session request received")
    
    session_id = uuid.uuid4()
    duration_hours = settings.SESSION_TIMEOUT_HOURS
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=duration_hours)
    
    # Step 1: Connect to database
    t_conn_start = time.perf_counter()
    async with get_db_connection() as conn:
        t_conn_end = time.perf_counter()
        db_conn_time = (t_conn_end - t_conn_start) * 1000
        
        # Step 2: Insert session
        t_insert_start = time.perf_counter()
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO sessions (session_id, expires_at)
                VALUES (%s, %s);
                """,
                (session_id, expires_at)
            )
        t_insert_end = time.perf_counter()
        sql_exec_time = (t_insert_end - t_insert_start) * 1000
        
    logger.info("Session created: %s", session_id)
    logger.info("Session expires_at: %s", expires_at)
    
    # Step 3: Serialize response
    t_response_start = time.perf_counter()
    response = SessionResponse(
        session_id=session_id,
        created_at=now,
        expires_at=expires_at
    )
    t_end = time.perf_counter()
    response_sent_time = (t_end - t_response_start) * 1000
    total_time = (t_end - t_start) * 1000
    
    logger.info("Database connection established (%.2f ms)", db_conn_time)
    logger.info("Session inserted (%.2f ms)", sql_exec_time)
    logger.info("Response sent (%.2f ms)", response_sent_time)
    logger.info("Total session creation time (%.2f ms)", total_time)
    
    # Check if any step exceeds 300ms
    if db_conn_time > 300:
        logger.warning("Database connection establishment exceeded 300 ms (%.2f ms).", db_conn_time)
    if sql_exec_time > 300:
        logger.warning("SQL execution exceeded 300 ms (%.2f ms).", sql_exec_time)
        
    return response
