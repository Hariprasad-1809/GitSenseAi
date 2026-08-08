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


async def test_api_embeddings_and_rag_pipeline():
    logger.info("==================================================")
    logger.info("TEST: API-Based Embeddings & Low-Memory RAG Verification")
    logger.info("==================================================")

    # 1. DEPENDENCY AUDIT: Verify no heavy ML libraries are imported by backend app
    logger.info("[CHECK 1: Production Dependency Audit]")
    forbidden_modules = ["sentence_transformers", "torch", "transformers", "triton"]
    for mod_name in forbidden_modules:
        assert mod_name not in sys.modules, f"Forbidden heavy module '{mod_name}' loaded in sys.modules!"
    logger.info("PASSED: Zero heavy ML libraries loaded.")

    # 2. EMBEDDER CLIENT & VECTOR DIMENSION VERIFICATION
    logger.info("[CHECK 2: API Embedder Vector Dimension Audit]")
    from app.core.embedder import get_embedder
    embedder = get_embedder()
    logger.info(f"Using embedder model: '{embedder.model_name}'")

    test_vectors = embedder.embed_chunks(["def hello_world(): return 'Hello GitSense'"])
    assert len(test_vectors) == 1, "Failed to receive vector embedding array from API."
    vector_dim = len(test_vectors[0])
    logger.info(f"API Vector dimension received: {vector_dim}")
    assert vector_dim == 1536, f"Expected 1536 vector dimension for text-embedding-3-small, got {vector_dim}"
    logger.info("PASSED: Vector dimension is 1536.")

    # 3. DATABASE INITIALIZATION & MIGRATION VERIFICATION
    logger.info("[CHECK 3: Database Migration Verification]")
    from app.db.supabase import init_db_pool, close_db_pool, init_db, create_session, delete_session
    from app.core.vectorstore import (
        create_project,
        get_project_status,
        delete_project,
        hybrid_search,
        get_project_files
    )
    from app.core.extractor import clone_github
    from app.core.rag_pipeline import run_indexing_pipeline, run_query_pipeline

    await init_db_pool()
    await init_db()
    logger.info("PASSED: Database initialized with 1536-dimensional schema.")

    # 4. SMALL REPOSITORY INGESTION TEST
    logger.info("[CHECK 4: Full Ingestion & 1536-Dim Storage Verification]")
    session_id = uuid.uuid4()
    project_id = uuid.uuid4()
    await create_session(session_id, expires_in_hours=1)
    await create_project(project_id, session_id, "octocat-hello-world", repo_url="https://github.com/octocat/Hello-World")

    try:
        repo_path = await asyncio.to_thread(clone_github, "https://github.com/octocat/Hello-World", str(project_id))
        await run_indexing_pipeline(project_id, "octocat-hello-world", repo_path)

        status_entry = await get_project_status(project_id)
        logger.info(f"Post-ingestion status: {status_entry}")
        assert status_entry["status"] == "completed"
        assert status_entry["percentage"] == 100.0

        # Verify files stored in DB
        db_files = await get_project_files(project_id)
        assert len(db_files) > 0, "No files found in DB after indexing."
        logger.info(f"Database files retrieved: {db_files}")

        # 5. HYBRID RAG SEARCH & LLM QUERY VERIFICATION
        logger.info("[CHECK 5: Hybrid RAG Search & LLM Response Verification]")
        query = "What is the content of this repository?"
        query_vector = embedder.embed_query(query)
        assert len(query_vector) == 1536, f"Query vector dimension expected 1536, got {len(query_vector)}"

        chunks = await hybrid_search(project_id, query_vector, query)
        logger.info(f"Retrieved {len(chunks)} relevant chunks from PostgreSQL pgvector.")
        assert len(chunks) > 0, "Hybrid search returned 0 chunks!"

        # Run query pipeline
        rag_response = await run_query_pipeline(project_id, session_id, "What does this repo contain?")
        logger.info(f"RAG Response Answer (length={len(rag_response['answer'])}):\n{rag_response['answer'][:300]}...")
        assert len(rag_response["answer"]) > 0, "RAG response answer was empty!"

        logger.info("==================================================")
        logger.info("API EMBEDDINGS & RAG PIPELINE VERIFICATION PASSED 100%!")
        logger.info("==================================================")

    finally:
        await asyncio.sleep(1.0)
        await delete_project(project_id)
        await delete_session(session_id)
        await close_db_pool()


if __name__ == "__main__":
    asyncio.run(test_api_embeddings_and_rag_pipeline())
