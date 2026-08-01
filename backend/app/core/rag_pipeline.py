import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID
import aiofiles
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
    Background worker task to walk a project directory, parse/chunk supported files,
    generate local embeddings, and save everything into PostgreSQL via psycopg.
    """
    logger.info(f"Starting indexing pipeline for project {project_name} ({project_id}) at {repo_path}")
    try:
        # Discover files to index
        all_files: List[Path] = []
        for p in repo_path.rglob("*"):
            if p.is_file() and should_index_file(p):
                all_files.append(p)

        total_files = len(all_files)
        logger.info(f"Discovered {total_files} files to index for project {project_id}")

        if total_files == 0:
            await update_project_status(
                project_id, 
                "completed", 
                files_processed=0, 
                total_files=0
            )
            return

        await update_project_status(
            project_id, 
            "processing", 
            files_processed=0, 
            total_files=total_files
        )

        files_processed = 0
        chunk_batch: List[Dict[str, Any]] = []
        file_entries: List[Dict[str, Any]] = []
        embedder = get_embedder()

        for file_path in all_files:
            relative_path = str(file_path.relative_to(repo_path)).replace("\\", "/")
            ext = file_path.suffix
            
            # Read file content asynchronously
            try:
                # Open without errors="ignore" to check for valid UTF-8 compatibility
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    content = await f.read()
            except (UnicodeDecodeError, ValueError):
                logger.warning(f"Skipping binary file: {file_path}")
                continue
            except Exception as e:
                logger.warning(f"Failed to read file {file_path}: {e}. Skipping.")
                continue

            # Ensure ingestion never fails because of one invalid file
            try:
                # Sanitize the file content before chunking
                content = sanitize_text(content)
                
                # Run chunking
                file_chunks = chunk_file(content, ext, str(project_id), relative_path)
                
                # Sanitize chunk contents
                for chunk in file_chunks:
                    chunk["content"] = sanitize_text(chunk["content"])
                
                chunk_batch.extend(file_chunks)
                
                file_entries.append({
                    "file_path": relative_path,
                    "language": ext.replace(".", "")
                })
                
                files_processed += 1
            except Exception as file_exc:
                logger.warning(f"Failed to process file {file_path}: {file_exc}. Skipping.")
                continue

            # Embed and insert chunks in batches to prevent memory bloat
            if len(chunk_batch) >= 100:
                try:
                    logger.info(f"Embedding batch of {len(chunk_batch)} chunks...")
                    for chunk in chunk_batch:
                        chunk["content"] = sanitize_text(chunk["content"])
                    
                    texts = [c["content"] for c in chunk_batch]
                    embeddings = embedder.embed_chunks(texts)
                    
                    for chunk, emb in zip(chunk_batch, embeddings):
                        chunk["embedding"] = emb
                        
                    await insert_chunks(chunk_batch)
                    chunk_batch.clear()
                except Exception as batch_exc:
                    logger.error(f"Failed to insert batch of chunks: {batch_exc}. Continuing.")
                    chunk_batch.clear()

            # Periodically update status in DB
            if files_processed % 10 == 0:
                await update_project_status(
                    project_id, 
                    "processing", 
                    files_processed=files_processed, 
                    total_files=total_files
                )

        # Process any remaining chunks
        if chunk_batch:
            try:
                logger.info(f"Embedding final batch of {len(chunk_batch)} chunks...")
                for chunk in chunk_batch:
                    chunk["content"] = sanitize_text(chunk["content"])
                
                texts = [c["content"] for c in chunk_batch]
                embeddings = embedder.embed_chunks(texts)
                
                for chunk, emb in zip(chunk_batch, embeddings):
                    chunk["embedding"] = emb
                    
                await insert_chunks(chunk_batch)
                chunk_batch.clear()
            except Exception as batch_exc:
                logger.error(f"Failed to insert final batch of chunks: {batch_exc}. Continuing.")
                chunk_batch.clear()

        # Save indexed file list
        try:
            if file_entries:
                await insert_project_files(project_id, file_entries)
        except Exception as e:
            logger.warning(f"Failed to save indexed file list metadata: {e}")

        # Mark indexing as completed
        await update_project_status(
            project_id, 
            "completed", 
            files_processed=files_processed, 
            total_files=total_files
        )
        logger.info(f"Indexing pipeline completed successfully for project {project_id}")

    except Exception as e:
        logger.error(f"Error during indexing pipeline for project {project_id}: {e}", exc_info=True)
        await update_project_status(
            project_id, 
            "failed", 
            error=str(e)
        )


def is_repository_summary_query(query: str) -> bool:
    """
    Classifies if the query seeks a repository-level summary or architectural layout.
    """
    q = query.lower().strip()
    keywords = [
        "summarize this repository",
        "summarize this project",
        "summarize the repository",
        "summarize the project",
        "explain this project",
        "explain this repository",
        "explain the project",
        "explain the repository",
        "describe the architecture",
        "describe the project architecture",
        "what does this repository do",
        "what does this project do",
        "what is this repository about",
        "what is this project about",
        "project architecture",
        "repository summary",
        "architecture of this project",
        "architecture of this repository"
    ]
    return any(kw in q for kw in keywords)


def format_context(chunks: List[Dict[str, Any]]) -> str:
    """
    Formats the context text. Each chunk is headed by its file path and line range.
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
    Uses hybrid search (or summary context retrieval) and queries Gemini 3.5 Flash.
    """
    logger.info("User question: '%s'", question)
    embedder = get_embedder()
    is_summary = is_repository_summary_query(question)

    if is_summary:
        logger.info(f"Repository Summary intent detected for query: '{question}'")
        # Retrieve representative chunks (READMEs, entry points, sample files)
        chunks = await retrieve_summary_context(project_id)
        
        system_prompt = (
            "You are GitSense AI, a principal software architect assistant. "
            "Your task is to summarize and explain the repository using ONLY the representative code chunks provided below.\n"
            "Generate a comprehensive, professional project summary answering the user's request. Include the following sections:\n"
            "1. Project Purpose (What does the project do?)\n"
            "2. High-Level Architecture (How is the code structured?)\n"
            "3. Key Technologies (Which libraries, frameworks, or databases are used?)\n"
            "4. Directory & Module Overview (What are the major folders and files?)\n"
            "5. Entry Points & Main Workflows (Where does execution start and how does it flow?)\n"
            "6. Recommended Starting Files (Where should a developer look first to understand the code?)\n\n"
            "Constraints:\n"
            "- Rely ONLY on the provided context. Do NOT make up information or assume.\n"
            "- Cite every statement or code structure by specifying its file path and line range (e.g., `app/main.py, Lines 10-25`).\n"
            "- If the context is insufficient to compile these sections, explain what you can strictly based on the available files."
        )
    else:
        logger.info(f"Standard query intent detected for query: '{question}'")
        # 1. Generate query embedding
        query_vector = embedder.embed_query(question)
        logger.info("Query embedding generated successfully. Dimensions: %d", len(query_vector))

        # 2. Perform hybrid search
        chunks = await hybrid_search(project_id, query_vector, question)

        system_prompt = (
            "You are GitSense AI, a helpful coding assistant designed to help developers explore and understand software repositories.\n"
            "Your task is to answer user questions using ONLY the retrieved code context provided below.\n\n"
            "Strict Constraints:\n"
            "1. Answer the question using ONLY the provided code snippets and files. Do NOT assume or extrapolate beyond the context.\n"
            "2. Cite every statement, explanation, or code reference by specifying the exact file path and line range (e.g., `app/main.py, Lines 10-25`).\n"
            "3. If the question asks about installing, running, building, or setting up the project, and the context includes configuration files (e.g., `package.json`, `requirements.txt`, etc.) or a `README.md`, you MUST use the scripts, dependencies, build/start tools, or project descriptions specified in those files to answer the user's question, and cite the relevant file paths and line ranges. You have explicit permission to explain how to execute the start/dev scripts listed in configuration files (e.g., `npm run dev` for `\"dev\": \"vite\"`).\n"
            "4. If the context does not contain enough information to answer the question, respond EXACTLY with: 'I don't have enough context.'\n"
            "5. Do NOT hallucinate. Do NOT cite files or lines not present in the context."
        )

    # Log context information before calling the LLM
    logger.info(
        "\n---------------------------------------\n"
        f"Retrieved Context Count: {len(chunks)}"
    )
    for idx, chunk in enumerate(chunks, start=1):
        score_val = chunk.get("score")
        score_str = f"{score_val:.6f}" if isinstance(score_val, float) else "N/A"
        logger.info(
            f"Chunk {idx}:\n"
            f"File: {chunk['file_path']} (Lines {chunk['start_line']}-{chunk['end_line']})\n"
            f"Score: {score_str}"
        )
    logger.info("---------------------------------------\n")

    # Build context and final prompt
    context_text = format_context(chunks)
    user_prompt = f"Retrieved Context:\n{context_text}\n\nUser Question: {question}\n\nAnswer:"

    # Call Gemini (OpenRouter backend)
    answer = await call_gemini_async(system_prompt, user_prompt)
    answer = answer.strip()

    # Formulate sources citation
    sources = []
    # If the LLM returned "I don't have enough context", we don't present sources
    if answer != "I don't have enough context.":
        for chunk in chunks:
            # We present the retrieved chunks as citations
            sources.append({
                "file_path": chunk["file_path"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "snippet": chunk["content"]
            })

    # Log trace counts for post-retrieval validation
    logger.info(
        "\nRetrieved chunk count: %d\n"
        "Prompt chunk count: %d\n"
        "Citation source count: %d\n"
        "Returned source count: %d",
        len(chunks), len(chunks), len(sources), len(sources)
    )

    # Save to chat history
    await insert_chat_history(session_id, project_id, question, answer, sources)

    return {
        "answer": answer,
        "sources": sources
    }
