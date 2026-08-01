import logging
import zipfile
from pathlib import Path
import git
from app.config import settings
from app.utils.file_cleanup import robust_rmtree

logger = logging.getLogger(__name__)


def extract_zip(zip_file_path: Path, project_id: str) -> Path:
    """
    Extracts a ZIP archive to the target repositories directory under the project_id.
    """
    target_dir = settings.repo_path / project_id
    target_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Extracting ZIP file {zip_file_path} to {target_dir}...")
    try:
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)
        logger.info(f"ZIP file successfully extracted to {target_dir}")
        return target_dir
    except Exception as e:
        logger.error(f"Failed to extract ZIP file: {e}")
        # Clean up directory on failure
        if target_dir.exists():
            robust_rmtree(target_dir)
        raise ValueError(f"Invalid ZIP archive: {e}")


def clone_github(repo_url: str, project_id: str) -> Path:
    """
    Clones a GitHub repository shallowly (depth=1, single_branch=True)
    to the target repositories directory under the project_id.
    """
    target_dir = settings.repo_path / project_id
    target_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Cloning GitHub repository {repo_url} to {target_dir}...")
    try:
        git.Repo.clone_from(
            url=repo_url,
            to_path=str(target_dir),
            depth=1,
            single_branch=True
        )
        logger.info(f"Successfully cloned repository {repo_url} to {target_dir}")
        return target_dir
    except Exception as e:
        logger.error(f"Failed to clone GitHub repository {repo_url}: {e}")
        # Clean up directory on failure
        if target_dir.exists():
            robust_rmtree(target_dir)
        raise ValueError(f"Failed to clone repository from URL. Verify repository exists and is public: {e}")


def cleanup_project_files(project_id: str) -> None:
    """
    Deletes the project's physical repository files from local storage.
    """
    target_dir = settings.repo_path / project_id
    if target_dir.exists():
        logger.info(f"Cleaning up files for project {project_id} at {target_dir}...")
        try:
            robust_rmtree(target_dir)
        except Exception as e:
            logger.warning(f"Error during cleanup of project {project_id} directory: {e}")
