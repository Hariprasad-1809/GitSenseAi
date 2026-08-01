import logging
from fastapi import APIRouter, status
from app.services.cleanup_service import run_cleanup

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/system", tags=["System"])


@router.post("/run-cleanup", status_code=status.HTTP_200_OK)
async def trigger_cleanup():
    """
    Manually triggers the background resource and session cleanup (development / admin endpoint).
    """
    logger.info("Manual cleanup triggered via API endpoint.")
    result = await run_cleanup()
    return {
        "status": "success",
        "message": "Cleanup job executed successfully.",
        "details": result
    }
