import logging
import uuid
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from app.config import settings
from app.core.extractor import clone_github, extract_zip
from app.core.rag_pipeline import run_indexing_pipeline
from app.core.vectorstore import get_project_status, update_project_status, create_project, list_projects
from app.models.schemas import GithubIngestRequest, IngestStatusResponse
from app.api.dependencies import get_active_session_id, validate_project_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest", tags=["Ingestion"])


async def process_zip_ingestion(project_id: uuid.UUID, zip_path: Path, filename: str) -> None:
    """
    Background task to extract ZIP archive and trigger indexing pipeline.
    Runs extraction in a thread pool to avoid blocking the event loop.
    """
    try:
        project_name = filename.rsplit(".", 1)[0]
        # Wrap blocking zip extraction in threadpool
        repo_path = await run_in_threadpool(extract_zip, zip_path, str(project_id))
        
        # Run indexing
        await run_indexing_pipeline(project_id, project_name, repo_path)
    except Exception as e:
        logger.error(f"Background ZIP ingestion failed for {project_id}: {e}", exc_info=True)
        await update_project_status(project_id, "failed", error=str(e))
    finally:
        # Delete temporary upload zip file
        if zip_path.exists():
            try:
                zip_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete temp ZIP file {zip_path}: {e}")


async def process_github_ingestion(project_id: uuid.UUID, repo_url: str) -> None:
    """
    Background task to clone GitHub repository shallowly and trigger indexing pipeline.
    Runs cloning in a thread pool to avoid blocking the event loop.
    """
    try:
        # Extract project name from URL (e.g. https://github.com/user/my-repo -> my-repo)
        url_path = repo_url.rstrip("/")
        project_name = url_path.split("/")[-1]
        if project_name.endswith(".git"):
            project_name = project_name[:-4]
            
        # Wrap blocking cloning operation in threadpool
        repo_path = await run_in_threadpool(clone_github, repo_url, str(project_id))
        
        # Run indexing
        await run_indexing_pipeline(project_id, project_name, repo_path)
    except Exception as e:
        logger.error(f"Background GitHub ingestion failed for {project_id}: {e}", exc_info=True)
        await update_project_status(project_id, "failed", error=str(e))


@router.post("/zip", status_code=status.HTTP_202_ACCEPTED)
async def ingest_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session_id: uuid.UUID = Depends(get_active_session_id)
):
    """
    Accepts multipart ZIP archive uploads, generates a project UUID, extracts files,
    and runs AST indexing in the background. Returns HTTP 202 immediately.
    """
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only ZIP archives are supported."
        )

    # Enforce one repository per session limit
    existing_projects = await list_projects(session_id)
    if existing_projects:
        logger.warning(f"Ingestion rejected: Session {session_id} already has an active repository.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session already has an active repository. Only one repository per session is allowed."
        )

    project_id = uuid.uuid4()
    
    # Save uploaded file temporarily to disk to keep memory consumption low
    temp_zip_path = settings.upload_path / f"{project_id}.zip"
    logger.info(f"Saving uploaded ZIP temporarily to {temp_zip_path}...")
    try:
        with open(temp_zip_path, "wb") as buffer:
            # Chunk read to prevent memory spikes
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
    except Exception as e:
        logger.error(f"Failed to write uploaded file to disk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save upload zip: {e}"
        )

    # Pre-register project status as queued
    await create_project(project_id, session_id, file.filename.rsplit(".", 1)[0])
    await update_project_status(project_id, "queued")

    # Queue background task
    background_tasks.add_task(process_zip_ingestion, project_id, temp_zip_path, file.filename)

    return {
        "project_id": str(project_id),
        "status": "queued",
        "message": "ZIP archive uploaded. Ingestion has been scheduled in the background."
    }


@router.post("/github", status_code=status.HTTP_202_ACCEPTED)
async def ingest_github(
    request: GithubIngestRequest,
    background_tasks: BackgroundTasks,
    session_id: uuid.UUID = Depends(get_active_session_id)
):
    """
    Clones a GitHub repository URL shallowly and indexes it in the background.
    Returns HTTP 202 immediately.
    """
    repo_url_str = str(request.repo_url)
    
    # Basic URL structure check
    if not ("github.com" in repo_url_str.lower() and (repo_url_str.startswith("http://") or repo_url_str.startswith("https://"))):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported repository host. Only public GitHub HTTPS repositories are supported."
        )

    # Enforce one repository per session limit
    existing_projects = await list_projects(session_id)
    if existing_projects:
        logger.warning(f"Ingestion rejected: Session {session_id} already has an active repository.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session already has an active repository. Only one repository per session is allowed."
        )

    project_id = uuid.uuid4()
    
    # Extract project name from URL
    url_path = repo_url_str.rstrip("/")
    project_name = url_path.split("/")[-1]
    if project_name.endswith(".git"):
        project_name = project_name[:-4]

    # Pre-register project status as queued
    await create_project(project_id, session_id, project_name, repo_url=repo_url_str)
    await update_project_status(project_id, "queued")

    # Queue background task
    background_tasks.add_task(process_github_ingestion, project_id, repo_url_str)

    return {
        "project_id": str(project_id),
        "status": "queued",
        "message": "GitHub repository request received. Cloning has been scheduled in the background."
    }


@router.get("/status/{project_id}", response_model=IngestStatusResponse)
async def get_ingestion_status(
    project_id: uuid.UUID = Depends(validate_project_session)
):
    """
    Returns the current ingestion status, file processing count, and errors of a project.
    """
    status_entry = await get_project_status(project_id)
    if not status_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found. Ensure the project_id is correct."
        )
        
    return status_entry
