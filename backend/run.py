import os
import sys
import asyncio
import logging
from pathlib import Path
import uvicorn

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("run")

if __name__ == "__main__":
    from app.config import settings

    app_dir = Path("app").resolve()
    data_dir = Path("data").resolve()
    repo_dir = settings.repo_path
    upload_dir = settings.upload_path
    scratch_dir = Path("scratch").resolve()

    # Ensure storage directories exist so Uvicorn FileFilter identifies them as directory exclusions
    data_dir.mkdir(parents=True, exist_ok=True)
    repo_dir.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    reload_dirs = [str(app_dir)]
    reload_excludes = [
        str(data_dir),
        str(repo_dir),
        str(upload_dir),
        str(scratch_dir),
    ]

    logger.info("Starting Uvicorn development server...")
    logger.info("Watched directories: %s", reload_dirs)
    logger.info("Excluded directories: %s", reload_excludes)
    logger.info("Repository clone directory: %s", str(repo_dir))

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=reload_dirs,
        reload_excludes=reload_excludes
    )

