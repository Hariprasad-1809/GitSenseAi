import os
import sys

# Add parent directory to sys.path so 'app' module can be imported when running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Set SelectorEventLoop on Windows to support psycopg async connections
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.api.routes_ingest import router as ingest_router
from app.api.routes_projects import router as projects_router
from app.api.routes_query import router as query_router
from app.api.routes_sessions import router as sessions_router
from app.api.routes_system import router as system_router
from app.db.supabase import init_db

# Configure logging format and level
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def cleanup_scheduler():
    """
    Background job that runs periodically to clean up expired sessions and resources.
    """
    from app.config import settings
    logger.info("Background resource cleanup scheduler started (running every %s minutes).", settings.CLEANUP_INTERVAL_MINUTES)
    while True:
        try:
            await asyncio.sleep(settings.CLEANUP_INTERVAL_MINUTES * 60)
            logger.info("Executing scheduled background resource cleanup job.")
            from app.services.cleanup_service import run_cleanup
            await run_cleanup()
        except asyncio.CancelledError:
            logger.info("Background resource cleanup task was cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in background cleanup scheduler: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler that runs database migrations/schema setups on startup,
    schedules the periodic background cleanup job, and cleans up tasks on shutdown.
    """
    logger.info("Starting up GitSense AI Backend...")
    try:
        # Initialize connection pool
        from app.db.supabase import init_db_pool, close_db_pool
        await init_db_pool()
        
        # Run database initialization
        await init_db()
        from app.config import settings
        logger.info("Loaded LLM_MODEL from environment:\n%s", settings.LLM_MODEL)
        logger.info("Session timeout: %d hours", settings.SESSION_TIMEOUT_HOURS)
        logger.info("Cleanup interval: %d minutes", settings.CLEANUP_INTERVAL_MINUTES)
    except Exception:
        logger.exception("Failed to initialize database during startup.")
        raise
    
    # Start background cleanup task
    cleanup_task = asyncio.create_task(cleanup_scheduler())
    
    try:
        yield
    finally:
        logger.info("Shutting down GitSense AI Backend...")
        # Cancel background cleanup task on shutdown
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        
        # Close connection pool
        await close_db_pool()


app = FastAPI(
    title="GitSense AI API",
    description="Production-ready backend for GitSense AI codebase exploration RAG application.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local development ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(sessions_router)
app.include_router(ingest_router)
app.include_router(query_router)
app.include_router(projects_router)
app.include_router(system_router)


from fastapi.exceptions import RequestValidationError


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Custom handler for validation errors (422) to return descriptive, developer-friendly messages.
    """
    errors = []
    for error in exc.errors():
        loc = " -> ".join(str(l) for l in error.get("loc", []))
        msg = error.get("msg", "Validation error")
        errors.append(f"Field '{loc}': {msg}")
    
    logger.warning(f"Request validation failed for endpoint '{request.method} {request.url.path}': {errors}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request validation failed.",
            "errors": errors
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global catch-all exception handler to return structured JSON errors instead of crashing with HTML.
    Logs endpoint, project_id, session_id, and masks sensitive database URLs.
    """
    endpoint = f"{request.method} {request.url.path}"
    session_id = request.headers.get("X-Session-ID") or request.query_params.get("session_id")
    
    # Try to extract project_id from path or query parameters
    project_id = request.path_params.get("project_id") or request.query_params.get("project_id")
    
    # Log detailed trace without leaking credentials
    log_msg = f"Unhandled system error occurred on endpoint={endpoint}"
    if session_id:
        log_msg += f", session_id={session_id}"
    if project_id:
        log_msg += f", project_id={project_id}"
        
    logger.error(f"{log_msg}: {exc}", exc_info=True)
    
    # Mask database credentials
    from app.db.supabase import mask_database_url
    detail_msg = mask_database_url(str(exc))
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": f"An unexpected error occurred. Please contact support. Error details: {detail_msg}"
        }
    )


@app.get("/health", tags=["System"])
async def health_check():
    """
    System status check endpoint.
    """
    return {
        "status": "healthy",
        "service": "GitSense AI Backend",
        "version": "1.0.0"
    }


@app.get("/", tags=["System"])
async def root():
    """
    Root endpoint directing users to documentation.
    """
    return {
        "message": "Welcome to the GitSense AI Backend API.",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
