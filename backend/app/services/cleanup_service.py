import logging
import asyncio
from pathlib import Path
from fastapi.concurrency import run_in_threadpool
from app.config import settings
from app.db.supabase import get_expired_sessions, delete_session, get_db_connection
from app.utils.file_cleanup import robust_rmtree

logger = logging.getLogger(__name__)


async def retry_cleanup_background(repo_path: Path, delay_seconds: int = 60) -> None:
    """
    Asynchronous background task to retry directory cleanup after a delay.
    """
    logger.info("Scheduled background cleanup retry for folder: %s after %ss", repo_path, delay_seconds)
    await asyncio.sleep(delay_seconds)
    logger.info("Executing background cleanup retry for: %s", repo_path)
    try:
        await run_in_threadpool(robust_rmtree, repo_path)
    except Exception as e:
        logger.error("Background cleanup retry failed for %s: %s", repo_path, e)


async def run_cleanup() -> dict:
    """
    Finds and removes all expired sessions and their associated physical/database resources.
    Cleans up in a safe, logical order:
    1. Delete vector embeddings, chunks, chat history, projects (via database cascade) and local disk folder.
    2. Deletes the session record.
    Returns a dictionary summarizing the cleanup results.
    """
    logger.info("Session and resource cleanup execution started.")
    cleaned_sessions = []
    errors = []
    
    try:
        # 1. Fetch expired sessions
        expired_sessions = await get_expired_sessions()
        logger.info(f"Discovered {len(expired_sessions)} expired sessions.")
        
        for sess in expired_sessions:
            session_id = sess["session_id"]
            logger.info(f"Session expiration triggered for session: {session_id}")
            
            # 2. Check if this session has a project associated with it
            project_id = None
            try:
                async with get_db_connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(
                            "SELECT id FROM projects WHERE session_id = %s;",
                            (session_id,)
                        )
                        row = await cur.fetchone()
                        if row:
                            project_id = row["id"]
            except Exception as e:
                logger.error(f"Error querying project for session {session_id}: {e}")
                errors.append(f"Query error for session {session_id}: {str(e)}")
            
            # 3. Clean up disk files first
            if project_id:
                repo_path = Path(settings.REPO_DIR) / str(project_id)
                if repo_path.exists():
                    try:
                        logger.info(f"Deleting cloned repository folder from disk: {repo_path}")
                        success = await run_in_threadpool(robust_rmtree, repo_path)
                        if success:
                            logger.info(f"Repository deletion successful: project_id={project_id}")
                        else:
                            logger.warning(f"Repository deletion failed (locked files) for {repo_path}. Scheduling background retry.")
                            asyncio.create_task(retry_cleanup_background(repo_path))
                    except Exception as e:
                        logger.error(f"Failed to delete repository directory {repo_path} from disk: {e}")
                        asyncio.create_task(retry_cleanup_background(repo_path))
                else:
                    logger.info(f"Repository directory {repo_path} does not exist on disk. Skipping.")
            
            # 4. Delete the session row from the database (cascades database cleanup)
            try:
                logger.info(f"Deleting session database records: session_id={session_id}")
                await delete_session(session_id)
                logger.info(f"Database cleanup completed: Deleted session {session_id} (and cascaded project & chat rows).")
                cleaned_sessions.append(str(session_id))
            except Exception as e:
                logger.error(f"Failed to delete session {session_id} from database: {e}")
                errors.append(f"Database cleanup error for session {session_id}: {str(e)}")

        # 5. Sweep REPO_DIR for any orphaned repository folders (not actively indexing)
        try:
            repo_base = settings.repo_path
            if repo_base.exists():
                # Query actively indexing project IDs from database
                active_indexing_ids = set()
                try:
                    async with get_db_connection() as conn:
                        async with conn.cursor() as cur:
                            await cur.execute(
                                "SELECT id FROM projects WHERE status IN ('processing', 'cloning', 'parsing', 'generating embeddings', 'saving');"
                            )
                            rows = await cur.fetchall()
                            active_indexing_ids = {str(r["id"]) for r in rows}
                except Exception as active_err:
                    logger.warning(f"Could not query active indexing projects during orphan sweep: {active_err}")

                for child in repo_base.iterdir():
                    if child.is_dir():
                        folder_name = child.name
                        if folder_name not in active_indexing_ids:
                            logger.info(f"[CLEANUP] Found leftover repository directory on disk: {child}. Cleaning up...")
                            await run_in_threadpool(robust_rmtree, child)
        except Exception as sweep_err:
            logger.warning(f"Error during orphaned repository sweep: {sweep_err}")

    except Exception as e:
        logger.error(f"Error during cleanup execution: {e}", exc_info=True)
        errors.append(f"Global cleanup error: {str(e)}")
        
    logger.info(f"Session and resource cleanup execution finished. Successfully cleaned {len(cleaned_sessions)} sessions.")
    return {
        "expired_discovered": len(expired_sessions) if 'expired_sessions' in locals() else 0,
        "cleaned_count": len(cleaned_sessions),
        "cleaned_sessions": cleaned_sessions,
        "errors": errors
    }
