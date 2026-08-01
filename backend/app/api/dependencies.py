import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import Header, Query, Depends, HTTPException, status
from app.db.supabase import get_session, delete_session, get_project_session_id

logger = logging.getLogger(__name__)


async def get_active_session_id(
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    session_id: Optional[str] = Query(None)
) -> uuid.UUID:
    """
    FastAPI dependency to retrieve and validate that the session is active and not expired.
    Accepts the session ID in X-Session-ID header or session_id query parameter.
    Raises HTTP 401 Unauthorized if the session ID is missing.
    Raises HTTP 422 Unprocessable Entity if the session ID is an invalid UUID format.
    Raises HTTP 410 Gone if the session does not exist or has expired.
    """
    target_str = x_session_id or session_id
    if not target_str:
        logger.warning("Session validation failed: Session ID is missing from headers and query parameters.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID is missing from headers (X-Session-ID) and query parameters (session_id)"
        )

    try:
        target_session_id = uuid.UUID(target_str)
    except ValueError:
        logger.warning("Session validation result: Session ID '%s' is not a valid UUID.", target_str)
        from fastapi.exceptions import RequestValidationError
        errors = [{
            "loc": ("header", "X-Session-ID"),
            "msg": "Input should be a valid UUID, invalid character: expected an optional prefix of `urn:uuid:` followed by [0-9a-fA-F-], found `i` at 1",
            "type": "uuid_parsing",
            "input": target_str
        }]
        raise RequestValidationError(errors)

    session = await get_session(target_session_id)
    if not session:
        logger.warning("Session validation result: Session %s not found in database.", target_session_id)
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Session expired"
        )

    # Check expiration
    now = datetime.now(timezone.utc)
    expires_at = session["expires_at"]
    
    # Ensure expires_at is timezone-aware
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
        
    if expires_at < now:
        logger.warning("Session validation result: Session %s expired (expired at %s, current host UTC time is %s).", target_session_id, expires_at, now)
        try:
            # Clean up project files on disk before deleting the session record
            from app.db.supabase import get_db_connection
            async with get_db_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT id FROM projects WHERE session_id = %s;",
                        (target_session_id,)
                    )
                    row = await cur.fetchone()
                    if row:
                        proj_id = row["id"]
                        logger.info(f"Lazy cleanup: found project {proj_id} for expired session {target_session_id}. Deleting files...")
                        from fastapi.concurrency import run_in_threadpool
                        from app.core.extractor import cleanup_project_files
                        await run_in_threadpool(cleanup_project_files, str(proj_id))
            
            await delete_session(target_session_id)
            logger.info("Successfully deleted expired session %s via lazy cleanup.", target_session_id)
        except Exception as e:
            logger.error("Error during lazy cleanup of expired session %s: %s", target_session_id, e, exc_info=True)
            
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Session expired"
        )

    logger.info("Session validation result: Session %s validated successfully.", target_session_id)
    return target_session_id


async def validate_project_session(
    project_id: uuid.UUID,
    session_id: uuid.UUID = Depends(get_active_session_id)
) -> uuid.UUID:
    """
    FastAPI dependency to validate that a project exists and belongs to the active session.
    Raises 404 if the project does not exist, and 403 if it belongs to a different session.
    """
    project_session_id = await get_project_session_id(project_id)
    if not project_session_id:
        logger.warning(f"Project validation failed: Project {project_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    if project_session_id != session_id:
        logger.warning(
            f"Unauthorized access attempt: Project {project_id} (owned by session {project_session_id}) "
            f"accessed by session {session_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: repository belongs to a different session"
        )

    return project_id
