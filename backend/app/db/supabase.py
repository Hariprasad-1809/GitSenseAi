import logging
import asyncio
import time
import uuid
import re
from urllib.parse import urlparse, urlunparse
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, List
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from supabase import create_client, Client
from app.config import settings

logger = logging.getLogger(__name__)


def mask_database_url(url: str) -> str:
    """Mask the password in a database connection URL or connection string."""
    if not url:
        return ""
    if url.startswith(("postgresql://", "postgres://")):
        try:
            parsed = urlparse(url)
            if parsed.password:
                netloc = parsed.netloc
                if "@" in netloc:
                    user_pass, host_port = netloc.rsplit("@", 1)
                    if ":" in user_pass:
                        username, _ = user_pass.split(":", 1)
                        masked_netloc = f"{username}:******@{host_port}"
                    else:
                        masked_netloc = f"{user_pass}:******@{host_port}"
                    parsed = parsed._replace(netloc=masked_netloc)
            return urlunparse(parsed)
        except Exception:
            pass
    try:
        return re.sub(r"(password\s*=\s*)(?:'[^']*'|\"[^\"]*\"|[^\s]+)", r"\1******", url, flags=re.IGNORECASE)
    except Exception:
        return "DATABASE_URL_MASK_FAILED"
# Initialize the official Supabase client inside a try-except block
# This prevents the app from crashing on startup if user credentials are mock/invalid placeholders.
# Direct psycopg connections to PostgreSQL will remain fully functional.
supabase_client = None
try:
    supabase_client = create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY
    )
except Exception as e:
    logger.warning(
        f"Official Supabase Client could not be initialized: {e}. "
        "Direct database operations via psycopg are unaffected."
    )


# Database connection pool global reference
db_pool: Optional[AsyncConnectionPool] = None


async def check_database_health() -> None:
    """
    Performs a pre-flight database connection check using a single one-off connection.
    Retries temporary network errors with exponential backoff, but fails fast on auth errors.
    """
    conninfo = settings.DATABASE_URL
    masked_url = mask_database_url(conninfo)
    logger.info("Pre-flight database connection check started on: %s", masked_url)
    
    retries = 3
    delay = 1.0
    
    for attempt in range(1, retries + 1):
        try:
            # Attempt a single one-off connection with a short timeout
            conn = await psycopg.AsyncConnection.connect(
                conninfo=conninfo,
                connect_timeout=5
            )
            # If successful, close it immediately and return
            await conn.close()
            logger.info("Pre-flight database credentials verification successful.")
            return
        except psycopg.OperationalError as e:
            err_msg = str(e)
            
            # Check for fatal authentication errors
            is_auth_error = any(
                phrase in err_msg.lower()
                for phrase in ["password authentication failed", "authentication failed", "too many authentication failures", "circuitbreaker"]
            )
            
            if is_auth_error:
                logger.error(
                    "DATABASE_STARTUP_ERROR: Database authentication failed. "
                    "Credentials in DATABASE_URL are invalid or blocked by circuit breaker: %s",
                    err_msg
                )
                raise RuntimeError(
                    f"Fatal database authentication failure on startup: {err_msg}. "
                    "Verify your database credentials and connection parameters."
                )
            
            # For temporary network errors, retry with backoff
            if attempt < retries:
                logger.warning(
                    "Database connection attempt %d failed (temporary network error): %s. "
                    "Retrying in %.1f seconds...",
                    attempt, err_msg, delay
                )
                await asyncio.sleep(delay)
                delay *= 2
            else:
                logger.error("DATABASE_STARTUP_ERROR: Failed to establish pre-flight connection after all retries: %s", err_msg)
                raise RuntimeError(f"Database connection could not be established after {retries} retries: {err_msg}")
        except Exception as e:
            logger.error("DATABASE_STARTUP_ERROR: Unexpected error during pre-flight check: %s", e)
            raise RuntimeError(f"Unexpected database connection failure: {e}")


async def init_db_pool() -> None:
    """
    Initializes the database connection pool.
    """
    global db_pool
    if db_pool is None:
        # Run pre-flight health check to ensure credentials are correct
        await check_database_health()
        
        logger.info("Initializing database connection pool...")
        logger.info("Connection pool URL: %s", mask_database_url(settings.DATABASE_URL))
        db_pool = AsyncConnectionPool(
            conninfo=settings.DATABASE_URL,
            min_size=1,
            max_size=4,
            max_idle=45.0,
            max_lifetime=300.0,
            timeout=10.0,
            kwargs={"row_factory": dict_row, "connect_timeout": 5},
            open=False
        )
        await db_pool.open()
        logger.info("Database connection pool initialized and opened successfully.")


async def close_db_pool() -> None:
    """
    Closes the database connection pool.
    """
    global db_pool
    if db_pool is not None:
        logger.info("Closing database connection pool...")
        await db_pool.close()
        db_pool = None
        logger.info("Database connection pool closed.")


@asynccontextmanager
async def get_db_connection() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    """
    Async context manager that yields a PostgreSQL database connection from the connection pool.
    Wraps the connection context in an auto-committing transaction block.
    """
    global db_pool
    if db_pool is None:
        logger.warning("Database connection pool was not initialized. Initializing on-demand...")
        await init_db_pool()

    async with db_pool.connection() as conn:
        async with conn.transaction():
            yield conn


async def init_db(schema_path: str = "app/db/schema.sql") -> None:
    """
    Initializes the database by executing the schema.sql script.
    Uses get_db_connection() to leverage the connection pool.
    """
    import os
    if not os.path.isabs(schema_path):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        resolved_path = os.path.join(current_dir, os.path.basename(schema_path))
        if os.path.exists(resolved_path):
            schema_path = resolved_path
            
    logger.info("Initializing database schema using: %s", schema_path)
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                if settings.RESET_DATABASE_ON_START:
                    logger.warning("RESET_DATABASE_ON_START is True. Executing destructive table drops...")
                    await cur.execute("DROP TABLE IF EXISTS chat_history CASCADE;")
                    await cur.execute("DROP TABLE IF EXISTS chunks CASCADE;")
                    await cur.execute("DROP TABLE IF EXISTS files CASCADE;")
                    await cur.execute("DROP TABLE IF EXISTS projects CASCADE;")
                    await cur.execute("DROP TABLE IF EXISTS sessions CASCADE;")
                await cur.execute(schema_sql)
                await cur.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS current_file TEXT DEFAULT '';")
                await cur.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;")
                await cur.execute("ALTER TABLE files ADD COLUMN IF NOT EXISTS file_hash VARCHAR(64);")
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        logger.exception("Failed to initialize database schema")
        raise


async def create_session(session_id: uuid.UUID, expires_in_hours: int = 3) -> None:
    """
    Creates a new session in the database with host-clock based expiration.
    """
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=expires_in_hours)
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO sessions (session_id, expires_at)
                VALUES (%s, %s);
                """,
                (session_id, expires_at)
            )


async def get_session(session_id: uuid.UUID) -> Optional[dict]:
    """
    Retrieves session metadata if it exists.
    """
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT session_id, created_at, expires_at
                FROM sessions
                WHERE session_id = %s;
                """,
                (session_id,)
            )
            return await cur.fetchone()


async def delete_session(session_id: uuid.UUID) -> None:
    """
    Deletes a session from the database (cascades deletes to project, chunks, files, history).
    """
    logger.info("Session deletion: %s", session_id)
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM sessions WHERE session_id = %s;",
                (session_id,)
            )


async def get_expired_sessions() -> List[dict]:
    """
    Retrieves all sessions that have expired based on the current host clock.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT session_id, expires_at
                FROM sessions
                WHERE expires_at < %s;
                """,
                (now,)
            )
            return await cur.fetchall()


async def get_project_session_id(project_id: uuid.UUID) -> Optional[uuid.UUID]:
    """
    Retrieves the session_id associated with a project.
    """
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT session_id FROM projects WHERE id = %s;",
                (project_id,)
            )
            row = await cur.fetchone()
            return row["session_id"] if row else None


async def get_cached_intelligence(project_id: uuid.UUID, cache_key: str) -> Optional[dict]:
    """
    Retrieves cached intelligence (summaries, graphs, workflows) for a project.
    """
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT cache_key, content, metadata, created_at
                FROM intelligence_cache
                WHERE project_id = %s AND cache_key = %s;
                """,
                (project_id, cache_key)
            )
            return await cur.fetchone()


async def save_cached_intelligence(project_id: uuid.UUID, cache_key: str, content: str, metadata: Optional[dict] = None) -> None:
    """
    Saves or updates cached intelligence for a project.
    """
    import json
    meta_json = json.dumps(metadata or {})
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO intelligence_cache (project_id, cache_key, content, metadata)
                VALUES (%s, %s, %s, %s::jsonb)
                ON CONFLICT (project_id, cache_key)
                DO UPDATE SET content = EXCLUDED.content, metadata = EXCLUDED.metadata, created_at = NOW();
                """,
                (project_id, cache_key, content, meta_json)
            )

