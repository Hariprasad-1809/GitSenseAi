# Temporary Storage Architecture & Lifecycle Specification

## 1. Overview & Motivation
GitSense AI is designed as a lightweight, cloud-native Retrieval-Augmented Generation (RAG) system for public and uploaded software repositories. In previous iterations, cloned repositories remained permanently on the backend server filesystem (under `backend/data/repos/<project_id>/`), leading to unbounded disk usage spikes, file descriptor leaks, and increased hosting infrastructure costs.

Under the **Temporary Storage Architecture**, repository source files exist on the backend local disk **only temporarily** during the active ingestion, AST parsing, embedding vector generation, and initial intelligence caching phases. Once persistent metadata, AST-aware code chunks, vector embeddings, and repository intelligence summaries are safely committed to PostgreSQL/Supabase, **the temporary local repository directory is automatically deleted**.

All subsequent application workflows—including vector search, semantic RAG Q&A, PDF export generation, and frontend file tree browsing—operate **100% from PostgreSQL / Supabase / pgvector**, eliminating server disk dependencies.

---

## 2. Storage Separation Matrix

| Storage Layer | Location / Target | Lifetime | Data Contents |
| :--- | :--- | :--- | :--- |
| **Temporary Disk Storage** | `backend/data/repos/<project_id>/` | Temporary (Active Ingestion Only) | Shallow Git clone (`depth=1`) / Extracted ZIP files |
| **Temporary Upload Storage** | `backend/data/uploads/<project_id>.zip` | Temporary (Upload Processing Only) | Raw uploaded `.zip` archives |
| **Persistent PostgreSQL Database** | Supabase / PostgreSQL | Persistent (Session Duration) | `projects`, `files` (with `size_bytes`), `chunks` (`vector(384)` + FTS), `chat_history`, `intelligence_cache` |
| **Embedding Model Cache** | User Cache / `SENTENCE_TRANSFORMERS_HOME` | Persistent (Application Level) | Pre-trained Sentence Transformers model weights (`BAAI/bge-small-en-v1.5`) |

---

## 3. Complete Ingestion & Cleanup Workflow

```text
       User Request (GitHub URL / ZIP Upload)
                        │
                        ▼
       [1] Create DB Project Record (status = 'queued')
                        │
                        ▼
       [2] Shallow Clone / Extract to Temporary Storage
           Path: backend/data/repos/<project_id>/
                        │
                        ▼
       [3] File Discovery & Incremental Hash Check
           - Compute SHA-256 hashes
           - Record exact file sizes (size_bytes)
                        │
                        ▼
       [4] Parallel AST Parsing & Chunking
           - Semaphore-bounded (16 workers)
           - Tree-sitter AST & Fallback chunking
                        │
                        ▼
       [5] Batched Embedding Generation
           - BAAI/bge-small-en-v1.5 (384 dims)
           - Vectorized embedding generation
                        │
                        ▼
       [6] Database Persistence Transaction
           - Save chunks & vector embeddings to `chunks` table
           - Save file paths, languages, size_bytes to `files` table
                        │
                        ▼
       [7] Phase 2 Intelligence Generation & Caching
           - Generate & cache `repo_summary`, `architecture_summary`, `workflow_summary`, `tech_stack` into `intelligence_cache`
                        │
                        ▼
       [8] Mark Ingestion Status Completed
           - status = 'completed', files_processed = total_files, percentage = 100%
                        │
                        ▼
       [9] Safe Temporary Directory Cleanup
           - Path boundary verification (path inside REPO_DIR)
           - Close Git handles & run garbage collection
           - Recursive directory removal (`robust_rmtree`)
                        │
                        ▼
       [10] Post-Ingestion Operations
           - Chat, RAG, File Tree serve 100% from PostgreSQL / Supabase
```

---

## 4. Post-Ingestion Endpoint Data Flow

### A. RAG Q&A Queries (`POST /api/query`)
- **No Local Files Required**: The query vector is generated using `get_embedder().embed_query(question)`.
- **Hybrid RRF Search**: Executes vector similarity search (`<=>`) and PostgreSQL Full-Text Keyword Search (`fts_vector @@ websearch_to_tsquery`) against the `chunks` table in Supabase.
- **Context Construction**: Formats retrieved code snippets directly from `chunks.content` and `chunks.file_path`.

### B. Project File Tree Browsing (`GET /api/projects/{project_id}/files`)
- **No Disk Inspection**: Queries the `files` database table.
- **Payload Response**: Returns `FileEntry(file_path, language, size_bytes)` directly from stored database rows, maintaining exact file sizes without disk access.

### C. Repository Intelligence (`get_or_generate_intelligence`)
- **Database Cache**: Fetches precomputed summaries from `intelligence_cache`.
- **Lazy Fallback**: If a cache miss occurs after local repository deletion, lazily constructs directory structure and sample context snippets from database `files` and `chunks` tables.

---

## 5. Cleanup Security & Path Boundary Protection

The cleanup engine (`backend/app/utils/file_cleanup.py`) enforces strict security validation before executing directory deletion:

1. **Path Boundary Check**: Verifies using `Path.resolve()` that target deletion paths are strictly contained within `settings.REPO_DIR` or `settings.UPLOAD_DIR`.
2. **Arbitrary Deletion Protection**: Explicitly rejects any path pointing to system roots, parent directories, or outside workspace locations.
3. **Windows File Lock Recovery**: Releases open GitPython `Repo` object handles, triggers explicit Python garbage collection (`gc.collect()`), clears read-only attributes via `remove_readonly`, and retries with exponential backoff (`[0.5s, 1.0s, 2.0s, 4.0s, 8.0s]`).

---

## 6. Session Expiration & Background Garbage Collection

- **Periodic Scheduler**: A background task (`cleanup_scheduler`) executes every `settings.CLEANUP_INTERVAL_MINUTES` (default: 30 minutes).
- **Session Expiration Sweep**: Queries `sessions` where `expires_at < NOW()`. Deletes database rows (cascading `projects`, `files`, `chunks`, `chat_history`, `intelligence_cache`) and removes associated local directories.
- **Orphan Directory Sweep**: Scans `backend/data/repos/` for any leftover folders. Compares folder IDs against database projects with active indexing statuses (`['processing', 'cloning', 'parsing', 'generating embeddings', 'saving']`). Safely deletes any unindexed or stale orphaned directories while protecting actively indexing projects.

---

## 7. Error Handling & Resilience Rules

- **Pre-Completion Failure**: If cloning, parsing, embedding, or database insertion fails, project status is set to `failed` with error details. The local folder is retained temporarily to allow debugging or retry, and is later cleaned up by the periodic cleanup scheduler.
- **Post-Completion Cleanup Warning**: If repository cleanup encounters temporary file lock errors AFTER database persistence and completion, **the project status remains `completed`**. A warning is logged and a background retry (`retry_cleanup_background`) is scheduled.

---

## 8. Storage & Performance Optimization

1. **Shallow Cloning**: Uses `git clone --depth 1 --single-branch` via GitPython to minimize network transfer and initial cloned disk footprint.
2. **Model Cache Isolation**: Model weights for Sentence Transformers are cached in standard user home directories (e.g. `~/.cache/torch/sentence_transformers`), completely separate from repository data directories.
3. **Batch Insertion**: Inserts chunks in 500-item database batches to optimize database transaction time.

---

## 9. Configuration Options

Environment configuration in `backend/.env` / `backend/app/config.py`:

```env
# Repository temporary storage directory
REPO_DIR=./data/repos

# Temporary upload storage directory
UPLOAD_DIR=./data/uploads

# Session expiration timeout (hours)
SESSION_TIMEOUT_HOURS=3

# Periodic background cleanup interval (minutes)
CLEANUP_INTERVAL_MINUTES=30
```
