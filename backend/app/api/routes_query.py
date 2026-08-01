import logging
import uuid
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from app.core.rag_pipeline import run_query_pipeline
from app.core.vectorstore import get_chat_history, get_project_status
from app.models.schemas import ChatHistoryEntry, QueryRequest, QueryResponse
from app.api.dependencies import get_active_session_id, validate_project_session

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Query"])


@router.post("/api/query", response_model=QueryResponse)
async def query_project(
    request: QueryRequest,
    session_id: uuid.UUID = Depends(get_active_session_id)
):
    """
    Answers a natural language developer question about a project repository.
    Uses hybrid search (semantic + keyword RRF) and Google Gemini 3.5 Flash.
    """
    # 1. Verify project exists, belongs to the session, and is fully indexed
    project_id = request.project_id
    await validate_project_session(project_id, session_id)

    proj_status = await get_project_status(project_id)
    if proj_status["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project is not ready for querying. Current status: '{proj_status['status']}'."
        )

    try:
        # Run query pipeline, passing session_id for chat history tracking
        res = await run_query_pipeline(project_id, session_id, request.question)
        return res
    except Exception as e:
        logger.error(f"Error executing query for project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while answering your question: {e}"
        )


@router.get("/api/projects/{project_id}/chat", response_model=List[ChatHistoryEntry])
async def get_project_chat_history(
    project_id: uuid.UUID = Depends(validate_project_session),
    session_id: uuid.UUID = Depends(get_active_session_id)
):
    """
    Retrieves the complete question-and-answer conversation log for a project.
    """
    try:
        history = await get_chat_history(project_id)
        return history
    except Exception as e:
        logger.error(f"Error fetching chat history for project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversation history: {e}"
        )
