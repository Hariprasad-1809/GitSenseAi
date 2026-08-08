import os
import stat
import shutil
import time
import gc
import logging
import git
from pathlib import Path

logger = logging.getLogger(__name__)


def remove_readonly(func, path, exc_info):
    """
    OnError handler for shutil.rmtree to remove read-only attribute and retry.
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        logger.debug("Failed to remove read-only attribute for %s: %s", path, e)


def robust_rmtree(path: Path) -> bool:
    """
    Robustly deletes a directory tree, resolving read-only file locks on Windows,
    closing GitPython repository objects, and retrying with exponential backoff.
    Verifies that target path is inside configured storage directories for security.
    Returns True if successfully deleted, False otherwise.
    """
    if not path.exists():
        return True

    from app.config import settings

    # Security check: Ensure target path is strictly inside REPO_DIR or UPLOAD_DIR
    try:
        resolved_target = path.resolve()
        allowed_dirs = [settings.repo_path.resolve(), settings.upload_path.resolve()]
        is_safe = any(
            resolved_target != allowed_dir and resolved_target.is_relative_to(allowed_dir)
            for allowed_dir in allowed_dirs
        )
        if not is_safe:
            logger.error(
                "[CLEANUP SECURITY REJECTION] Refusing to delete path '%s'. Path is not inside allowed repository directories: %s",
                resolved_target, allowed_dirs
            )
            return False
    except Exception as path_err:
        logger.error("[CLEANUP SECURITY REJECTION] Error validating path boundary for '%s': %s", path, path_err)
        return False

    logger.info("[CLEANUP] Cleaning temporary repository directory: %s", path)

    # Close any GitPython repo objects and run garbage collection
    try:
        for obj in gc.get_objects():
            try:
                if isinstance(obj, git.Repo):
                    obj.close()
            except Exception:
                pass
    except Exception as e:
        logger.debug("Error closing git repositories: %s", e)

    # Run garbage collection to release file descriptors/locks
    gc.collect()

    backoffs = [0.5, 1.0, 2.0, 4.0, 8.0]
    max_retries = len(backoffs)

    for attempt in range(max_retries + 1):
        try:
            shutil.rmtree(path, onerror=remove_readonly)
            if not path.exists():
                logger.info("Repository removed successfully.")
                return True
        except Exception as e:
            if attempt < max_retries:
                sleep_time = backoffs[attempt]
                logger.warning(
                    "Retry %s... Deletion failed for %s due to: %s. Retrying in %ss...",
                    attempt + 1, path, e, sleep_time
                )
                time.sleep(sleep_time)
                gc.collect()
            else:
                logger.error(
                    "Failed to delete repository directory %s after %s retries. Locked file/directory: %s",
                    path, max_retries, e
                )

    return False
