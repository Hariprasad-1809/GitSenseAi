import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID
import aiofiles
from fastapi.concurrency import run_in_threadpool
from app.core.chunker import chunk_file
from app.core.embedder import get_embedder
from app.core.llm import call_gemini_async
from app.core.vectorstore import (
    create_project,
    insert_chunks,
    insert_project_files,
    update_project_status,
    hybrid_search,
    retrieve_summary_context,
    insert_chat_history
)
from app.utils.file_filters import should_index_file
from app.utils.text_sanitizer import sanitize_text

logger = logging.getLogger(__name__)



async def run_indexing_pipeline(project_id: UUID, project_name: str, repo_path: Path) -> None:
    """
    High-performance parallel indexing pipeline.
    1. File Discovery & Incremental Hash Check (skips unchanged files)
    2. Concurrent AST Parsing via threadpool and semaphore-bounded workers
    3. Batched Vectorized Embedding Generation
    4. Async Database Chunk Insertion & File Registry Update
    5. Sets status to 'completed' immediately to enable fast chatting (<25s for small repos, <60s for medium repos)
    6. Asynchronously launches Phase 2 Background Intelligence Workers
    """
    import time
    from app.core.chunker import compute_file_hash

def audit_and_read_files(repo_path: Path, existing_hashes: Dict[str, str]) -> tuple:
    """
    Synchronous helper executed in threadpool to perform directory discovery,
    file reading, size stat, and SHA-256 hash calculation without blocking event loop.
    """
    from app.core.chunker import compute_file_hash
    from app.utils.file_filters import should_index_file

    all_file_paths: List[Path] = []
    for p in repo_path.rglob("*"):
        if p.is_file() and should_index_file(p):
            all_file_paths.append(p)

    files_to_process: List[tuple[Path, str, str]] = []
    all_file_entries: List[Dict[str, Any]] = []
    current_rel_paths = set()

    for p in all_file_paths:
        rel_path = str(p.relative_to(repo_path)).replace("\\", "/")
        current_rel_paths.add(rel_path)
        ext = p.suffix.lower().replace(".", "") or "plain"

        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            fhash = compute_file_hash(content)
            size_bytes = p.stat().st_size
        except Exception:
            content = ""
            fhash = ""
            size_bytes = 0

        all_file_entries.append({
            "file_path": rel_path,
            "language": ext,
            "file_hash": fhash,
            "size_bytes": size_bytes
        })

        if existing_hashes.get(rel_path) == fhash and fhash != "":
            pass
        else:
            files_to_process.append((p, rel_path, fhash))

    return all_file_paths, files_to_process, all_file_entries, current_rel_paths


async def run_indexing_pipeline(project_id: UUID, project_name: str, repo_path: Path) -> None:
    """
    High-performance non-blocking parallel indexing pipeline.
    All synchronous I/O and CPU-intensive operations (cloning, file discovery, SHA-256 hashing,
    AST parsing, PyTorch embeddings, cleanup) are offloaded to worker threads via asyncio.to_thread / run_in_threadpool.
    """
    import time
    logger.info(f"[INGEST TIMING] Ingestion started for project '{project_name}' ({project_id}) at {repo_path}")
    t0 = time.perf_counter()

    try:
        # Pre-load embedder singleton instance in background thread if not already loaded
        embedder = await asyncio.to_thread(get_embedder)

        # 1. Non-blocking File Discovery & Hash Audit (offloaded to threadpool)
        from app.core.vectorstore import get_existing_file_hashes, delete_file_chunks
        existing_hashes = await get_existing_file_hashes(project_id)

        t_audit_start = time.perf_counter()
        all_file_paths, files_to_process, all_file_entries, current_rel_paths = await asyncio.to_thread(
            audit_and_read_files, repo_path, existing_hashes
        )
        t_audit = time.perf_counter() - t_audit_start

        total_discovered = len(all_file_paths)
        logger.info(f"[INGEST TIMING] File discovery & hash audit finished in {t_audit:.2f}s. Discovered {total_discovered} files.")

        if total_discovered == 0:
            await update_project_status(project_id, "completed", files_processed=0, total_files=0, current_file="")
            from app.core.extractor import cleanup_project_files
            await asyncio.to_thread(cleanup_project_files, str(project_id))
            return

        await update_project_status(
            project_id, "parsing", files_processed=0, total_files=total_discovered, current_file="Checking incremental file hashes..."
        )

        # Cleanup deleted files from vector storage
        deleted_paths = [path for path in existing_hashes if path not in current_rel_paths]
        if deleted_paths:
            logger.info(f"Removing {len(deleted_paths)} deleted files from vector storage...")
            await delete_file_chunks(project_id, deleted_paths)

        # Cleanup modified files before re-inserting
        modified_paths = [rel for _, rel, _ in files_to_process if rel in existing_hashes]
        if modified_paths:
            logger.info(f"Removing old chunks for {len(modified_paths)} modified files...")
            await delete_file_chunks(project_id, modified_paths)

        logger.info(f"Incremental indexing audit: {len(all_file_paths) - len(files_to_process)} unchanged files skipped, {len(files_to_process)} files queued for parallel indexing.")

        if not files_to_process:
            # All files are up to date!
            from app.core.intelligence_engine import run_background_intelligence_worker
            asyncio.create_task(run_background_intelligence_worker(project_id, project_name, repo_path))
            await update_project_status(project_id, "completed", files_processed=total_discovered, total_files=total_discovered, current_file="")
            logger.info(f"[INGEST] Project marked completed: {project_id}")
            from app.core.extractor import cleanup_project_files
            await asyncio.to_thread(cleanup_project_files, str(project_id))
            return

        # 2. Parallel Parsing Workers (Tree-sitter AST & Fallback)
        t_parse_start = time.perf_counter()
        semaphore = asyncio.Semaphore(16)
        parsed_chunks: List[Dict[str, Any]] = []
        files_completed = len(all_file_paths) - len(files_to_process)

        async def parse_worker(p: Path, rel_path: str, fhash: str) -> List[Dict[str, Any]]:
            nonlocal files_completed
            async with semaphore:
                ext = p.suffix.lower()
                try:
                    async with aiofiles.open(p, "r", encoding="utf-8") as f:
                        content = await f.read()
                    content = sanitize_text(content)
                    chunks = await asyncio.to_thread(chunk_file, content, ext, str(project_id), rel_path)
                    for c in chunks:
                        c["content"] = sanitize_text(c["content"])
                    
                    files_completed += 1
                    if files_completed % 10 == 0 or files_completed == total_discovered:
                        await update_project_status(
                            project_id, "parsing", files_processed=files_completed, total_files=total_discovered, current_file=rel_path
                        )
                    return chunks
                except Exception as file_err:
                    logger.warning(f"Failed to parse file '{rel_path}': {file_err}")
                    files_completed += 1
                    return []

        tasks = [parse_worker(p, rel, fhash) for p, rel, fhash in files_to_process]
        results = await asyncio.gather(*tasks)
        for chunk_list in results:
            parsed_chunks.extend(chunk_list)

        t_parse = time.perf_counter() - t_parse_start
        logger.info(f"[INGEST TIMING] AST parsing finished in {t_parse:.2f}s. Generated {len(parsed_chunks)} chunks from {len(files_to_process)} files.")

        # 3. Batched Embedding Generation (Offloaded to worker thread)
        if parsed_chunks:
            await update_project_status(
                project_id, "generating embeddings", files_processed=total_discovered, total_files=total_discovered, current_file=f"Embedding {len(parsed_chunks)} code chunks in parallel batches..."
            )
            t_emb_start = time.perf_counter()
            texts = [c["content"] for c in parsed_chunks]
            embeddings = await asyncio.to_thread(embedder.embed_chunks, texts, 64)
            
            for chunk, emb in zip(parsed_chunks, embeddings):
                chunk["embedding"] = emb

            t_emb = time.perf_counter() - t_emb_start
            logger.info(f"[INGEST TIMING] Embedding generation finished in {t_emb:.2f}s.")

            await update_project_status(
                project_id, "saving", files_processed=total_discovered, total_files=total_discovered, current_file="Writing vector chunks to database..."
            )
            
            # 4. Database Persistence
            t_db_start = time.perf_counter()
            batch_size = 500
            for i in range(0, len(parsed_chunks), batch_size):
                await insert_chunks(parsed_chunks[i : i + batch_size])
            t_db = time.perf_counter() - t_db_start
            logger.info(f"[INGEST TIMING] Database chunk persistence finished in {t_db:.2f}s.")

        # Save project files metadata
        await insert_project_files(project_id, all_file_entries)

        t_total = time.perf_counter() - t0
        logger.info(f"[INGEST TIMING] Phase 1 fast indexing completed in {t_total:.2f}s for project '{project_name}' ({project_id}).")

        # 5. Enable Instant Chat Readiness (Mark Status Completed & 100%)
        await update_project_status(
            project_id, "completed", files_processed=total_discovered, total_files=total_discovered, current_file=""
        )
        logger.info(f"[INGEST] Project status set to completed (100%): {project_id}")

        # 6. Spawn Phase 2 Asynchronous Background Intelligence Worker (detached)
        from app.core.intelligence_engine import run_background_intelligence_worker
        logger.info(f"Spawning Phase 2 detached background worker task for project {project_id}...")
        asyncio.create_task(run_background_intelligence_worker(project_id, project_name, repo_path))

        # 7. Delete temporary cloned repository folder in worker thread
        from app.core.extractor import cleanup_project_files
        logger.info(f"[CLEANUP] Removing temporary repository: {repo_path}")
        try:
            await asyncio.to_thread(cleanup_project_files, str(project_id))
            if not repo_path.exists():
                logger.info(f"[CLEANUP] Temporary repository deleted successfully: {repo_path}")
            else:
                logger.warning(f"[CLEANUP] Temporary repository cleanup warning (locked files): {repo_path}")
        except Exception as cleanup_err:
            logger.warning(f"[CLEANUP] Temporary repository cleanup error after indexing for {project_id}: {cleanup_err}")
            from app.services.cleanup_service import retry_cleanup_background
            asyncio.create_task(retry_cleanup_background(repo_path))

    except Exception as e:
        logger.error(f"Error during parallel indexing pipeline for project {project_id}: {e}", exc_info=True)
        await update_project_status(
            project_id, "failed", files_processed=0, total_files=0, current_file="", error=str(e)
        )


def format_context(chunks: List[Dict[str, Any]]) -> str:
    """
    Formats context text for LLM prompts. Each chunk is headed by its file path and line range.
    """
    formatted_blocks = []
    for chunk in chunks:
        header = f"File: {chunk['file_path']}, Lines {chunk['start_line']}-{chunk['end_line']}"
        if chunk.get("symbol_name"):
            header += f" (Symbol: {chunk['symbol_name']}, Type: {chunk['symbol_type']})"
        block = f"[{header}]\n{chunk['content']}\n"
        formatted_blocks.append(block)
    return "\n".join(formatted_blocks)


async def run_query_pipeline(project_id: UUID, session_id: UUID, question: str) -> Dict[str, Any]:
    """
    Resolves user Q&A query against indexed codebase.
    Uses intent classification, pre-cached intelligence, hybrid RRF search with multi-factor reranking, and specialized prompts.
    """
    from app.core.query_classifier import classify_query
    from app.core.intelligence_engine import get_or_generate_intelligence

    logger.info("User question: '%s'", question)
    embedder = get_embedder()
    
    # 1. Classify query intent
    intent_info = classify_query(question)
    logger.info(f"Query intent classified as: {intent_info['intent']} (Cache Key: {intent_info.get('cache_key')})")

    # 2. Architectural / Backbone / Workflow / Summary Queries -> Intelligence Cache + Multi-Factor Reranked Context
    if intent_info.get("requires_summary") or intent_info["intent"] in ("ARCHITECTURE", "REPOSITORY_SUMMARY", "WORKFLOW"):
        cache_key = intent_info.get("cache_key") or "architecture_summary"
        cached_intelligence = await get_or_generate_intelligence(
            project_id,
            cache_key,
            project_name="indexed_codebase"
        )

        # Retrieve top code chunks as supplementary context
        query_vector = embedder.embed_query(question)
        supplementary_chunks = await hybrid_search(project_id, query_vector, question)
        supp_context = format_context(supplementary_chunks[:4]) if supplementary_chunks else "No supplementary chunks."

        system_prompt = (
            "You are GitSense AI, a Principal AI Engineer and Senior Software Architect.\n"
            "Provide a comprehensive, highly accurate architectural response to the user query.\n\n"
            "Format your answer with clear markdown headings and bullet points using the following structure:\n"
            "1. Executive Summary (Concise high-level answer directly addressing the question)\n"
            "2. Project Overview & Architectural Backbone (Core architecture, purpose, design philosophy)\n"
            "3. Folder Structure & Subsystem Responsibilities (Directory layout and key component roles)\n"
            "4. Main Modules & Component Boundaries (Core classes, services, routers, models)\n"
            "5. Request Lifecycle & Execution Flow (Step-by-step workflow from entrypoint to output)\n"
            "6. API Flow & Data Persistence (Routes, database, state management)\n"
            "7. Technology Stack & Key Design Patterns (Frameworks, libraries, structural patterns)\n"
            "8. Related Key Files, Classes & Functions (List exact file paths and symbol names)\n"
            "9. Potential Architectural Improvements (Performance, scalability, code quality suggestions)\n\n"
            "Always cite real file paths and symbols mentioned in the context."
        )
        user_prompt = (
            f"Codebase Architectural Intelligence:\n{cached_intelligence}\n\n"
            f"Relevant Code Chunks Context:\n{supp_context}\n\n"
            f"User Question: {question}\n\n"
            "Provide a thorough, expert response:"
        )

        answer = await call_gemini_async(system_prompt, user_prompt)
        answer = answer.strip()

        sources = [
            {
                "file_path": chunk["file_path"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "snippet": chunk["content"]
            }
            for chunk in supplementary_chunks[:4]
        ]

        await insert_chat_history(session_id, project_id, question, answer, sources)
        return {
            "answer": answer,
            "sources": sources
        }

    # 3. Code Implementation / API / Bug / Performance Queries -> Multi-Factor Reranked Search
    query_vector = embedder.embed_query(question)
    chunks = await hybrid_search(project_id, query_vector, question)

    system_prompt = (
        "You are GitSense AI, a Principal Software Engineer and Codebase Expert.\n"
        "Answer the user question using the retrieved codebase chunks below.\n\n"
        "Instructions:\n"
        "1. Executive Summary: Begin with a concise 2-3 sentence executive summary answering the question.\n"
        "2. Technical Breakdown: Provide deep technical explanations referencing exact file paths and line ranges.\n"
        "3. Component Relationships: Explain how related classes, methods, endpoints, and configs interact.\n"
        "4. Factual Accuracy: Never say 'I don't have enough context' unless retrieval returned zero chunks."
    )

    logger.info(f"Retrieved {len(chunks)} top multi-factor reranked chunks for query.")
    context_text = format_context(chunks)
    user_prompt = f"Retrieved Code Context:\n{context_text}\n\nUser Question: {question}\n\nAnswer:"

    answer = await call_gemini_async(system_prompt, user_prompt)
    answer = answer.strip()

    sources = []
    if answer != "I don't have enough context.":
        for chunk in chunks:
            sources.append({
                "file_path": chunk["file_path"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "snippet": chunk["content"]
            })

    await insert_chat_history(session_id, project_id, question, answer, sources)

    return {
        "answer": answer,
        "sources": sources
    }

