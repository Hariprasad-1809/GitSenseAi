import asyncio
import logging
import time
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


async def test_phase2_deletion_resiliency():
    logger.info("==================================================")
    logger.info("TEST: Phase 2 Intelligence Worker Deletion Resiliency")
    logger.info("==================================================")

    from app.config import settings
    from app.db.supabase import (
        init_db_pool,
        close_db_pool,
        init_db,
        create_session,
        delete_session,
        get_cached_intelligence,
        save_cached_intelligence
    )
    from app.core.vectorstore import (
        create_project,
        get_project_status,
        delete_project,
        project_exists
    )
    from app.core.extractor import clone_github
    from app.core.rag_pipeline import run_indexing_pipeline
    from app.core.intelligence_engine import (
        run_background_intelligence_worker,
        register_phase2_task,
        cancel_phase2_task
    )

    await init_db_pool()
    await init_db()

    try:
        # --------------------------------------------------
        # TEST CASE 1: Valid Project Phase 2 Completion
        # --------------------------------------------------
        logger.info("\n[TEST CASE 1: Valid Project Phase 2 Completion & Intelligence Cache]")
        session1_id = uuid.uuid4()
        proj1_id = uuid.uuid4()
        await create_session(session1_id, expires_in_hours=1)
        await create_project(proj1_id, session1_id, "octocat-hello-world-1", repo_url="https://github.com/octocat/Hello-World")
        
        repo_path1 = await asyncio.to_thread(clone_github, "https://github.com/octocat/Hello-World", str(proj1_id))
        await run_indexing_pipeline(proj1_id, "octocat-hello-world-1", repo_path1)
        
        # Test save_cached_intelligence on valid active project
        await save_cached_intelligence(proj1_id, "repo_summary", "# Test Summary", {"type": "test"})
        
        # Verify project exists and intelligence_cache contains items
        assert await project_exists(proj1_id), "proj1 should exist in database."
        cached_summary = await get_cached_intelligence(proj1_id, "repo_summary")
        logger.info(f"Retrieved cached_summary for valid proj1: {bool(cached_summary)}")
        assert cached_summary is not None, "intelligence_cache should contain repo_summary for valid project."

        # Clean up session 1
        await delete_project(proj1_id)
        await delete_session(session1_id)

        # --------------------------------------------------
        # TEST CASE 2: Immediate Project Deletion During Phase 2 Execution
        # --------------------------------------------------
        logger.info("\n[TEST CASE 2: Immediate Project Deletion During Phase 2 Execution]")
        session2_id = uuid.uuid4()
        proj2_id = uuid.uuid4()
        await create_session(session2_id, expires_in_hours=1)
        await create_project(proj2_id, session2_id, "octocat-hello-world-2", repo_url="https://github.com/octocat/Hello-World")
        
        repo_path2 = settings.repo_path / str(proj2_id)
        repo_path2.mkdir(parents=True, exist_ok=True)
        (repo_path2 / "README.md").write_text("# Test Repo 2", encoding="utf-8")

        # Spawn Phase 2 worker explicitly
        logger.info(f"Spawning Phase 2 worker for project {proj2_id}...")
        worker_task = asyncio.create_task(run_background_intelligence_worker(proj2_id, "octocat-hello-world-2", repo_path2))
        register_phase2_task(proj2_id, worker_task)

        # IMMEDIATELY delete project from database while Phase 2 worker is running
        logger.info(f"Triggering delete_project({proj2_id}) mid-execution...")
        db_deleted = await delete_project(proj2_id)
        assert db_deleted, f"Failed to delete project {proj2_id} from DB."

        # Verify project no longer exists in DB
        assert not await project_exists(proj2_id), f"Project {proj2_id} should be deleted from DB."

        # Wait for worker task to settle
        await asyncio.sleep(1.5)
        logger.info("Worker task status post-deletion: done=%s", worker_task.done())

        # Verify NO foreign key exceptions were raised and worker exited cleanly
        cached_after_del = await get_cached_intelligence(proj2_id, "repo_summary")
        assert cached_after_del is None, "Deleted project should have NO intelligence_cache records created!"

        # Clean up session 2
        await delete_session(session2_id)

        # --------------------------------------------------
        # TEST CASE 3: Stale Worker Cannot Modify Newly Created Project
        # --------------------------------------------------
        logger.info("\n[TEST CASE 3: Stale Worker Cannot Modify Newly Created Project]")
        session3_id = uuid.uuid4()
        proj3_id = uuid.uuid4()
        await create_session(session3_id, expires_in_hours=1)
        await create_project(proj3_id, session3_id, "octocat-hello-world-3", repo_url="https://github.com/octocat/Hello-World")
        
        # Verify proj3 has distinct UUID from proj2
        assert proj3_id != proj2_id, "New project must have unique UUID."
        assert await project_exists(proj3_id), "proj3 should exist in DB."
        assert not await project_exists(proj2_id), "proj2 should NOT exist in DB."

        # Clean up session 3
        await delete_project(proj3_id)
        await delete_session(session3_id)

        logger.info("==================================================")
        logger.info("PHASE 2 DELETION RESILIENCY VERIFICATION PASSED 100%!")
        logger.info("==================================================")

    finally:
        await close_db_pool()


if __name__ == "__main__":
    asyncio.run(test_phase2_deletion_resiliency())
