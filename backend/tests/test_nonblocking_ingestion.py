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


async def test_nonblocking_status_polling():
    logger.info("==================================================")
    logger.info("TEST: Non-Blocking Event Loop & Status Polling Performance")
    logger.info("==================================================")

    from app.config import settings
    from app.db.supabase import init_db_pool, close_db_pool, init_db, create_session, delete_session
    from app.core.vectorstore import (
        create_project,
        get_project_status,
        delete_project
    )
    from app.core.extractor import clone_github
    from app.core.rag_pipeline import run_indexing_pipeline

    # 1. Initialize DB Pool & Schema, Pre-load Embedder Model
    await init_db_pool()
    await init_db()
    from app.core.embedder import get_embedder
    await asyncio.to_thread(get_embedder)

    session_id = uuid.uuid4()
    project_id = uuid.uuid4()
    await create_session(session_id, expires_in_hours=1)
    await create_project(project_id, session_id, "octocat-hello-world", repo_url="https://github.com/octocat/Hello-World")

    repo_dir = settings.repo_path / str(project_id)

    try:
        # 2. Start Background Ingestion Task
        logger.info("Spawning background ingestion task...")
        
        async def background_ingestion():
            repo_path = await asyncio.to_thread(clone_github, "https://github.com/octocat/Hello-World", str(project_id))
            await run_indexing_pipeline(project_id, "octocat-hello-world", repo_path)

        ingestion_task = asyncio.create_task(background_ingestion())

        # 3. CONCURRENT STATUS POLLING: Issue rapid status checks while background ingestion runs
        logger.info("Polling GET status concurrently while background ingestion runs...")
        poll_latencies = []
        statuses_seen = []

        while not ingestion_task.done():
            t_start = time.perf_counter()
            status_entry = await get_project_status(project_id)
            latency_ms = (time.perf_counter() - t_start) * 1000.0
            
            if status_entry:
                poll_latencies.append(latency_ms)
                status_name = status_entry.get("status")
                pct = status_entry.get("percentage")
                statuses_seen.append((status_name, pct))
                logger.info(f"Status Poll: status='{status_name}', pct={pct}%, latency={latency_ms:.2f}ms")
                
                # Assert status check responds in under 1500ms
                assert latency_ms < 1500.0, f"Status check blocked for too long! Latency: {latency_ms:.2f}ms"
                
            await asyncio.sleep(0.1)

        await ingestion_task
        logger.info("Background ingestion task finished.")

        # 4. FINAL STATUS & PROGRESS ASSERTIONS
        final_status = await get_project_status(project_id)
        logger.info(f"Final status check: {final_status}")

        assert final_status["status"] == "completed", f"Final status should be 'completed', got: {final_status['status']}"
        assert final_status["percentage"] == 100.0, f"Percentage should reach 100.0% only at completed, got: {final_status['percentage']}"

        # 5. LATENCY SUMMARY
        avg_latency = sum(poll_latencies) / max(1, len(poll_latencies))
        max_latency = max(poll_latencies) if poll_latencies else 0.0
        logger.info(f"Status Polling Latency Audit ({len(poll_latencies)} checks):")
        logger.info(f"  Average Latency: {avg_latency:.2f} ms")
        logger.info(f"  Maximum Latency: {max_latency:.2f} ms")
        logger.info(f"  Statuses Observed: {set([s[0] for s in statuses_seen])}")

        assert max_latency < 1500.0, f"Maximum latency exceeded threshold: {max_latency:.2f}ms"
        assert avg_latency < 800.0, f"Average latency exceeded threshold: {avg_latency:.2f}ms"

        logger.info("==================================================")
        logger.info("NON-BLOCKING CONCURRENCY VERIFICATION PASSED 100%!")
        logger.info("==================================================")

    finally:
        await asyncio.sleep(2.0)
        await delete_project(project_id)
        await delete_session(session_id)
        await close_db_pool()


if __name__ == "__main__":
    asyncio.run(test_nonblocking_status_polling())
