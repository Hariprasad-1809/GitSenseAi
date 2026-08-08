import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from psycopg.types.json import Jsonb
from app.db.supabase import get_db_connection
from app.utils.text_sanitizer import sanitize_text

logger = logging.getLogger(__name__)


async def create_project(project_id: UUID, session_id: UUID, name: str, repo_url: Optional[str] = None) -> None:
    """
    Creates a new project record in the database.
    """
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO projects (id, session_id, name, repo_url, status, started_at)
                VALUES (%s, %s, %s, %s, 'processing', NOW())
                ON CONFLICT (id) DO UPDATE
                SET session_id = EXCLUDED.session_id, name = EXCLUDED.name, repo_url = EXCLUDED.repo_url, 
                    status = 'processing', started_at = NOW(), completed_at = NULL, error = NULL;
                """,
                (project_id, session_id, name, repo_url)
            )


async def update_project_status(
    project_id: UUID, 
    status: str, 
    files_processed: int = 0, 
    total_files: int = 0, 
    current_file: Optional[str] = None,
    error: Optional[str] = None
) -> None:
    """
    Updates the indexing status of a project, including current_file being processed.
    """
    curr_file_val = current_file or ""
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            if status in ("completed", "failed"):
                await cur.execute(
                    """
                    UPDATE projects
                    SET status = %s, files_processed = %s, total_files = %s, current_file = %s, error = %s, completed_at = NOW()
                    WHERE id = %s;
                    """,
                    (status, files_processed, total_files, curr_file_val, error, project_id)
                )
            else:
                await cur.execute(
                    """
                    UPDATE projects
                    SET status = %s, files_processed = %s, total_files = %s, current_file = %s, error = %s
                    WHERE id = %s;
                    """,
                    (status, files_processed, total_files, curr_file_val, error, project_id)
                )


async def get_existing_file_hashes(project_id: UUID) -> Dict[str, str]:
    """
    Retrieves stored file_path -> file_hash mapping for a project to support incremental indexing.
    """
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT file_path, file_hash
                FROM files
                WHERE project_id = %s;
                """,
                (project_id,)
            )
            rows = await cur.fetchall()
            return {r["file_path"]: (r["file_hash"] or "") for r in rows}


async def delete_file_chunks(project_id: UUID, file_paths: List[str]) -> None:
    """
    Deletes metadata records and chunks for modified or deleted files.
    """
    if not file_paths:
        return
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM chunks WHERE project_id = %s AND file_path = ANY(%s);",
                (project_id, file_paths)
            )
            await cur.execute(
                "DELETE FROM files WHERE project_id = %s AND file_path = ANY(%s);",
                (project_id, file_paths)
            )


async def insert_project_files(project_id: UUID, file_entries: List[Dict[str, Any]]) -> None:
    """
    Inserts file metadata records (with file_hash and size_bytes) into the files table.
    """
    if not file_entries:
        return
        
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.executemany(
                """
                INSERT INTO files (project_id, file_path, language, file_hash, size_bytes)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (project_id, file_path) 
                DO UPDATE SET file_hash = EXCLUDED.file_hash, language = EXCLUDED.language, size_bytes = EXCLUDED.size_bytes;
                """,
                [(project_id, f["file_path"], f["language"], f.get("file_hash", ""), f.get("size_bytes", 0)) for f in file_entries]
            )


async def insert_chunks(chunks: List[Dict[str, Any]]) -> None:
    """
    Inserts a list of syntax-aware chunks with their vector embeddings into the chunks table.
    """
    if not chunks:
        return
        
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            # Prepare data tuple list
            params = []
            for chunk in chunks:
                # pgvector expects list of floats, serializable to '[val1,val2,...]' or passed directly
                embedding = chunk["embedding"]
                
                # Sanitize the content and key string metadata fields
                content = sanitize_text(chunk["content"])
                file_path = sanitize_text(chunk["file_path"])
                language = sanitize_text(chunk["language"])
                symbol_name = chunk.get("symbol_name")
                if symbol_name is not None:
                    symbol_name = sanitize_text(symbol_name)
                symbol_type = chunk.get("symbol_type")
                if symbol_type is not None:
                    symbol_type = sanitize_text(symbol_type)
                parent_class = chunk.get("parent_class")
                if parent_class is not None:
                    parent_class = sanitize_text(parent_class)
                
                meta_json = Jsonb(chunk.get("metadata", {}))
                params.append((
                    UUID(chunk["project_id"]),
                    file_path,
                    language,
                    symbol_name,
                    symbol_type,
                    parent_class,
                    chunk["start_line"],
                    chunk["end_line"],
                    content,
                    embedding,
                    chunk["chunking_method"],
                    meta_json
                ))
                
            await cur.executemany(
                """
                INSERT INTO chunks (
                    project_id, file_path, language, symbol_name, 
                    symbol_type, parent_class, start_line, end_line, 
                    content, embedding, chunking_method, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s, %s);
                """,
                params
            )



async def get_project_status(project_id: UUID) -> Optional[Dict[str, Any]]:
    """
    Retrieves the ingestion status of a project, including calculated percentage and current file.
    """
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id as project_id, session_id, name as project_name, repo_url, status, files_processed, total_files, current_file, started_at, completed_at, error
                FROM projects
                WHERE id = %s;
                """,
                (project_id,)
            )
            row = await cur.fetchone()
            if not row:
                return None
                
            total = row.get("total_files", 0) or 0
            processed = row.get("files_processed", 0) or 0
            pct = round((processed / total) * 100.0, 1) if total > 0 else 0.0
            row["percentage"] = pct
            return row


async def list_projects(session_id: UUID) -> List[Dict[str, Any]]:
    """
    Retrieves all projects in the database for a session with file count, language breakdown, and ingestion date.
    """
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            # Query projects for session
            await cur.execute(
                """
                SELECT id as project_id, name as project_name, started_at as ingestion_date, status, files_processed as file_count
                FROM projects
                WHERE session_id = %s
                ORDER BY created_at DESC;
                """,
                (session_id,)
            )
            projects = await cur.fetchall()
            
            result = []
            for p in projects:
                # Query language summary count from files table for each project
                await cur.execute(
                    """
                    SELECT language, COUNT(*) as cnt
                    FROM files
                    WHERE project_id = %s
                    GROUP BY language;
                    """,
                    (p["project_id"],)
                )
                langs = await cur.fetchall()
                lang_summary = {l["language"]: l["cnt"] for l in langs}
                
                result.append({
                    "project_id": p["project_id"],
                    "project_name": p["project_name"],
                    "language_summary": lang_summary,
                    "file_count": p["file_count"],
                    "ingestion_date": p["ingestion_date"],
                    "status": p["status"]
                })
            return result


async def delete_project(project_id: UUID) -> bool:
    """
    Deletes a project record from the database. References are set to ON DELETE CASCADE
    so this cleans up files, chunks, and chat history.
    """
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM projects WHERE id = %s;", (project_id,))
            return cur.rowcount > 0


async def get_project_files(project_id: UUID) -> List[Dict[str, Any]]:
    """
    Retrieves the complete flat list of files for a project including size_bytes.
    """
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT file_path, language, size_bytes
                FROM files
                WHERE project_id = %s
                ORDER BY file_path ASC;
                """,
                (project_id,)
            )
            return await cur.fetchall()


async def hybrid_search(project_id: UUID, query_vector: List[float], query_text: str) -> List[Dict[str, Any]]:
    """
    Executes advanced hybrid search (Semantic pgvector + FTS Keyword search),
    fetches 20 candidates per arm, and applies multi-factor reranking (RRF + architectural importance + symbol weight).
    """
    k = 60
    semantic_results: List[Dict[str, Any]] = []
    keyword_results: List[Dict[str, Any]] = []

    # Detect setup/running queries
    q = query_text.lower()
    run_keywords = ["run", "install", "start", "setup", "build", "deploy", "execute", "dependencies", "requirements", "clone", "how to"]
    is_run_query = any(kw in q for kw in run_keywords)

    config_results = []
    if is_run_query:
        logger.info("Setup/running query detected. Fetching project configuration/documentation files.")
        try:
            async with get_db_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        WITH ranked_chunks AS (
                            SELECT id, file_path, language, symbol_name, symbol_type, 
                                   parent_class, start_line, end_line, content,
                                   ROW_NUMBER() OVER (PARTITION BY LOWER(file_path) ORDER BY start_line ASC) as rn
                            FROM chunks
                            WHERE project_id = %s AND (
                                LOWER(file_path) LIKE '%%readme%%' OR 
                                LOWER(file_path) LIKE '%%package.json' OR 
                                LOWER(file_path) LIKE '%%requirements.txt' OR
                                LOWER(file_path) LIKE '%%dockerfile%%'
                            )
                        )
                        SELECT id, file_path, language, symbol_name, symbol_type, 
                               parent_class, start_line, end_line, content
                        FROM ranked_chunks
                        WHERE rn <= 3
                        ORDER BY start_line ASC;
                        """,
                        (project_id,)
                    )
                    config_results = await cur.fetchall()
            logger.info("Found %d config/README chunks to inject.", len(config_results))
        except Exception as e:
            logger.error("Failed to fetch config/README chunks: %s", e)

    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            # 1. Semantic search (fetch 20 candidates)
            await cur.execute(
                """
                SELECT id, file_path, language, symbol_name, symbol_type, 
                       parent_class, start_line, end_line, content, metadata,
                       (1 - (embedding <=> %s::vector)) as similarity
                FROM chunks
                WHERE project_id = %s
                ORDER BY embedding <=> %s::vector
                LIMIT 20;
                """,
                (query_vector, project_id, query_vector)
            )
            all_semantic = await cur.fetchall()
            semantic_results = [r for r in all_semantic if r.get("similarity", 0.0) >= 0.25]

            # 2. Keyword search (fetch 20 candidates) using websearch_to_tsquery
            await cur.execute(
                """
                SELECT id, file_path, language, symbol_name, symbol_type, 
                       parent_class, start_line, end_line, content, metadata,
                       ts_rank_cd(fts_vector, websearch_to_tsquery('english', %s)) as rank
                FROM chunks
                WHERE project_id = %s AND fts_vector @@ websearch_to_tsquery('english', %s)
                ORDER BY rank DESC
                LIMIT 20;
                """,
                (query_text, project_id, query_text)
            )
            keyword_results = await cur.fetchall()

    if config_results:
        semantic_candidates = config_results + semantic_results
        keyword_candidates = config_results + keyword_results
    else:
        semantic_candidates = semantic_results
        keyword_candidates = keyword_results

    # 3. Multi-Factor Reranking (RRF + Architectural Importance)
    rrf_scores = {}
    doc_map = {}

    for rank, doc in enumerate(semantic_candidates, start=1):
        doc_id = doc["id"]
        doc_map[doc_id] = doc
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (k + rank))

    for rank, doc in enumerate(keyword_candidates, start=1):
        doc_id = doc["id"]
        doc_map[doc_id] = doc
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (k + rank))

    # Apply architectural importance and symbol weight multipliers
    final_scores = {}
    entrypoint_indicators = ("main", "app", "index", "server", "router", "service", "controller", "config", "readme")

    for doc_id, base_score in rrf_scores.items():
        doc = doc_map[doc_id]
        multiplier = 1.0

        # File importance boost
        fpath = str(doc.get("file_path", "")).lower()
        if any(ind in fpath for ind in entrypoint_indicators):
            multiplier += 0.25

        # AST Symbol type boost (structured definitions > raw blocks)
        stype = str(doc.get("symbol_type", "")).lower()
        if stype in ("class", "method", "function", "interface", "struct"):
            multiplier += 0.20

        # Semantic similarity scaling if present
        sim = doc.get("similarity")
        if sim is not None:
            multiplier += float(sim) * 0.30

        final_scores[doc_id] = base_score * multiplier

    # Log hybrid stage details
    logger.info("Multi-factor Reranked search audit stats:")
    logger.info("  User query: '%s'", query_text)
    logger.info("  Semantic candidate count: %d", len(semantic_results))
    logger.info("  Keyword candidate count: %d", len(keyword_results))
    logger.info("  Total unique RRF candidates: %d", len(final_scores))

    # Sort documents by final multi-factor score descending
    sorted_ids = sorted(final_scores.keys(), key=lambda x: final_scores[x], reverse=True)

    # Select top 8 best chunks and attach computed score
    top_8 = []
    for doc_id in sorted_ids[:8]:
        doc = doc_map[doc_id]
        doc["score"] = final_scores[doc_id]
        top_8.append(doc)

    logger.info("  Selected Top %d best chunks after multi-factor reranking.", len(top_8))
    return top_8



async def retrieve_summary_context(project_id: UUID) -> List[Dict[str, Any]]:
    """
    Retrieves representative context for Repository-Level summary queries:
    - README files
    - Main entrypoints / configuration files (e.g. main.py, package.json, index.js, pom.xml, settings.py)
    - One representative chunk from each unique major directory
    """
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            # 1. Fetch README chunks
            await cur.execute(
                """
                SELECT id, file_path, language, symbol_name, symbol_type, 
                       parent_class, start_line, end_line, content
                FROM chunks
                WHERE project_id = %s AND (file_path ILIKE '%%readme.md' OR file_path ILIKE '%%readme.txt')
                ORDER BY start_line ASC
                LIMIT 10;
                """,
                (project_id,)
            )
            readme_chunks = await cur.fetchall()

            # 2. Fetch entrypoints chunks
            await cur.execute(
                """
                SELECT id, file_path, language, symbol_name, symbol_type, 
                       parent_class, start_line, end_line, content
                FROM chunks
                WHERE project_id = %s AND (
                    file_path ILIKE '%%main.py' OR 
                    file_path ILIKE '%%index.js' OR 
                    file_path ILIKE '%%index.ts' OR 
                    file_path ILIKE '%%app.py' OR
                    file_path ILIKE '%%package.json' OR
                    file_path ILIKE '%%pom.xml'
                )
                ORDER BY start_line ASC
                LIMIT 10;
                """,
                (project_id,)
            )
            entrypoint_chunks = await cur.fetchall()

            # 3. Fetch one representative chunk from each folder/file module to understand modules layout
            await cur.execute(
                """
                SELECT DISTINCT ON (file_path) 
                       id, file_path, language, symbol_name, symbol_type, 
                       parent_class, start_line, end_line, content
                FROM chunks
                WHERE project_id = %s
                ORDER BY file_path, symbol_type NULLS LAST, id ASC
                LIMIT 20;
                """,
                (project_id,)
            )
            module_chunks = await cur.fetchall()

    # Combine and de-duplicate by chunk ID
    seen_ids = set()
    combined = []
    
    for chunk in (readme_chunks + entrypoint_chunks + module_chunks):
        if chunk["id"] not in seen_ids:
            seen_ids.add(chunk["id"])
            combined.append(chunk)
            
    # Limit summary context size to avoid exploding token window (e.g. max 25 chunks)
    return combined[:25]


async def insert_chat_history(
    session_id: UUID,
    project_id: UUID, 
    question: str, 
    answer: str, 
    sources: List[Dict[str, Any]]
) -> None:
    """
    Stores a Q&A conversation record in the chat history.
    """
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO chat_history (session_id, project_id, question, answer, sources)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (session_id, project_id, question, answer, Jsonb(sources))
            )


async def get_chat_history(project_id: UUID) -> List[Dict[str, Any]]:
    """
    Retrieves the Q&A conversation history for a project.
    """
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, question, answer, sources, created_at
                FROM chat_history
                WHERE project_id = %s
                ORDER BY created_at ASC;
                """,
                (project_id,)
            )
            rows = await cur.fetchall()
            # Deserialize sources JSON
            result = []
            for row in rows:
                result.append({
                    "id": row["id"],
                    "question": row["question"],
                    "answer": row["answer"],
                    # psycopg handles jsonb automatic parsing if row factory is dict_row and registered,
                    # otherwise it returns python dict directly
                    "sources": row["sources"] if isinstance(row["sources"], list) else json.loads(row["sources"]),
                    "created_at": row["created_at"]
                })
            return result
