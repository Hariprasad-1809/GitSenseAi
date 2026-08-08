import asyncio
import logging
import uuid
import sys
from pathlib import Path

# Set SelectorEventLoop on Windows for psycopg async compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_temporary_storage_lifecycle():
    logger.info("==================================================")
    logger.info("TEST: Temporary Storage Lifecycle & DB Verification")
    logger.info("==================================================")

    from app.config import settings
    from app.db.supabase import init_db_pool, close_db_pool, init_db, create_session, delete_session
    from app.core.vectorstore import (
        create_project,
        get_project_status,
        get_project_files,
        delete_project,
        hybrid_search
    )
    from app.core.extractor import clone_github, cleanup_project_files
    from app.core.rag_pipeline import run_indexing_pipeline
    from app.core.embedder import get_embedder
    from app.core.intelligence_engine import get_or_generate_intelligence
    from app.utils.file_cleanup import robust_rmtree

    # 1. Initialize DB Pool
    await init_db_pool()
    await init_db()

    # 2. Test Security Boundary Check on robust_rmtree
    logger.info("Checking security boundary check in robust_rmtree...")
    forbidden_path = Path("C:/Windows/System32") if sys.platform == "win32" else Path("/usr/bin")
    is_deleted = robust_rmtree(forbidden_path)
    assert not is_deleted, "Security check failed: robust_rmtree allowed deleting path outside REPO_DIR!"
    logger.info("Security boundary check PASSED.")

    # 3. Create Test Session and Project
    session_id = uuid.uuid4()
    project_id = uuid.uuid4()
    await create_session(session_id, expires_in_hours=1)
    await create_project(project_id, session_id, "octocat-hello-world", repo_url="https://github.com/octocat/Hello-World")

    repo_dir = settings.repo_path / str(project_id)

    try:
        # 4. Clone test repository
        logger.info(f"Cloning test repository to {repo_dir}...")
        clone_github("https://github.com/octocat/Hello-World", str(project_id))
        assert repo_dir.exists(), f"Repository directory should exist after cloning: {repo_dir}"
        logger.info("Repository cloned successfully.")

        # 5. Run Ingestion Pipeline
        logger.info("Running indexing pipeline...")
        await run_indexing_pipeline(project_id, "octocat-hello-world", repo_dir)

        # 6. Verify Status Reached Completed
        status_info = await get_project_status(project_id)
        logger.info(f"Project status after indexing: {status_info}")
        assert status_info["status"] == "completed", f"Status should be 'completed', got: {status_info['status']}"
        assert status_info["percentage"] == 100.0, f"Percentage should be 100.0, got: {status_info['percentage']}"

        # 7. VERIFY FILESYSTEM: Cloned repository directory MUST NOT exist after successful indexing!
        logger.info("Verifying local repository directory cleanup...")
        assert not repo_dir.exists(), f"CRITICAL REQUIREMENT FAILED: Local repository directory still exists at {repo_dir}"
        logger.info("VERIFICATION PASSED: Local repository directory has been deleted!")

        # 8. VERIFY DATABASE PERSISTENCE: Files & Chunks exist in PostgreSQL
        files = await get_project_files(project_id)
        logger.info(f"Retrieved {len(files)} files from database: {files}")
        assert len(files) > 0, "Files table should contain indexed files!"
        assert "size_bytes" in files[0], "Files record must contain size_bytes!"
        assert files[0]["size_bytes"] > 0, "size_bytes should be non-zero for non-empty files!"

        # 9. VERIFY QUERY PIPELINE: RAG hybrid search operates 100% from PostgreSQL
        logger.info("Testing RAG hybrid search query after local repo deletion...")
        embedder = get_embedder()
        query_text = "What is this repository about?"
        query_vector = embedder.embed_query(query_text)
        chunks = await hybrid_search(project_id, query_vector, query_text)
        logger.info(f"Retrieved {len(chunks)} search chunks from PostgreSQL pgvector.")
        assert len(chunks) > 0, "RAG search must return relevant chunks from database!"

        # 10. VERIFY INTELLIGENCE CACHE & LAZY FALLBACK
        logger.info("Testing repository intelligence lookup after local repo deletion...")
        summary = await get_or_generate_intelligence(project_id, "repo_summary", "octocat-hello-world")
        logger.info(f"Intelligence summary retrieved (length={len(summary)}): {summary[:150]}...")
        assert len(summary) > 0, "Intelligence summary should not be empty!"

        logger.info("==================================================")
        logger.info("ALL TEMPORARY STORAGE LIFECYCLE TESTS PASSED 100%!")
        logger.info("==================================================")

    finally:
        # Clean up database test records & any leftover session
        await delete_project(project_id)
        await delete_session(session_id)
        await close_db_pool()


if __name__ == "__main__":
    asyncio.run(test_temporary_storage_lifecycle())
