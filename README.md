# GitSense AI — Context-Aware Codebase Intelligence & RAG System

GitSense AI is an enterprise-grade, high-performance **Retrieval-Augmented Generation (RAG)** platform designed specifically for deep codebase comprehension, interactive Q&A, and technical architecture analysis. It ingests public GitHub repositories or uploaded ZIP archives, parses syntax structures using **Tree-sitter AST nodes**, computes dense **1536-dimensional vector embeddings**, stores vectors in **PostgreSQL + pgvector (Supabase)**, and synthesizes cited answers using **OpenRouter LLMs**.

---
Live Link: https://git-sense-ai.vercel.app
## Table of Contents

- [Problem Statement](#problem-statement)
- [What GitSense AI Does](#what-gitsense-ai-does)
- [Main Features](#main-features)
- [System Architecture Overview](#system-architecture-overview)
- [Technology Stack](#technology-stack)
- [Database & Vector Storage Architecture](#database--vector-storage-architecture)
- [Retrieval-Augmented Generation (RAG) Pipeline](#retrieval-augmented-generation-rag-pipeline)
- [AI / LLM Synthesis Architecture](#ai--llm-synthesis-architecture)
- [Repository Ingestion Lifecycle](#repository-ingestion-lifecycle)
- [Query & Chat Workflow](#query--chat-workflow)
- [Session & Project Lifecycles](#session--project-lifecycles)
- [Immediate Delete & Cleanup Lifecycle](#immediate-delete--cleanup-lifecycle)
- [Browser Refresh & SPA Routing Behavior](#browser-refresh--spa-routing-behavior)
- [API Endpoints Overview](#api-endpoints-overview)
- [Frontend-Backend Communication](#frontend-backend-communication)
- [Environment Configuration](#environment-configuration)
- [Local Development Setup](#local-development-setup)
- [Production Cloud Deployment](#production-cloud-deployment)
- [Project Directory Structure](#project-directory-structure)
- [Security & Ephemeral Resource Isolation](#security--ephemeral-resource-isolation)
- [Error Handling & Resiliency](#error-handling--resiliency)
- [Performance Optimization & Low-Memory Footprint](#performance-optimization--low-memory-footprint)
- [Known Limitations](#known-limitations)
- [Future Enhancements](#future-enhancements)

---

## Problem Statement

Large codebases are difficult to navigate, onboard to, and audit. Traditional tools face major issues:
1. **Token Limit Constraints**: Standard Large Language Models (LLMs) cannot accept multi-megabyte code repositories directly within context windows.
2. **Loss of Syntax Context**: Naive text chunking (splitting code every 500 characters or fixed lines) breaks function boundaries, separates docstrings from method bodies, and confuses variable scopes.
3. **High Resource Requirements**: Loading heavy local ML models (e.g. PyTorch, CUDA, SentenceTransformers) on cloud backends requires gigabytes of RAM, causing low-memory hosting platforms (e.g. Render free 512 MiB instances) to crash during build or deployment.
4. **Stale Cloned Repository Storage**: Persisting cloned repositories on server disks rapidly exhausts cloud hosting storage space.

GitSense AI solves all of these challenges with an **AST-aware, low-memory API embedding pipeline, ephemeral directory auto-deletion, pgvector hybrid search, and single-page routing resiliency**.

---

## What GitSense AI Does

- **Shallow Cloning & Fast Extraction**: Clones public GitHub repositories with `depth=1` or extracts ZIP archives into temporary session-isolated directories.
- **AST Code Parsing**: Uses **Tree-sitter** to extract complete structural nodes (functions, classes, methods) alongside adjacent docstrings and comment blocks.
- **1536-Dimensional API Vector Embeddings**: Uses OpenAI's `text-embedding-3-small` via API with dynamic batching (100 items/call) and exponential backoff retries, using **<50 MB RAM** at runtime.
- **pgvector Hybrid Search**: Combines 1536-dim vector cosine similarity with PostgreSQL Full-Text Keyword Search (`websearch_to_tsquery('english', query)`), merged using Reciprocal Rank Fusion (RRF).
- **Cited Architectural Synthesis**: Generates response text referencing exact source files and line ranges (e.g., `[File: main.py, Lines 15-42]`).
- **100% Temporary Storage Guarantee**: Deletes local cloned repositories **immediately** after indexing and database persistence.
- **Ephemeral Session Security**: Automatically expires sessions, database rows, and files after 3 hours (`SESSION_TIMEOUT_HOURS=3`), enforced by an automated background worker running every 10 minutes.

---

## Main Features

- ⚡ **AST-Aware Syntax Chunking**: Preserves structural integrity across Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, PHP, and Ruby.
- 🚀 **Low-Memory Cloud Footprint**: Runs easily on 512 MiB RAM cloud instances with zero heavy local ML dependencies (`torch`, `sentence-transformers`, `CUDA` purged).
- 🔍 **Hybrid Multi-Factor Retrieval**: Blends dense semantic vector similarity with sparse keyword lexical search using RRF ranking.
- 📄 **Citations**: Cites file paths and line ranges for every technical claim.
- 📊 **Phase 2 Intelligence Cache**: Automatically pre-computes executive summaries, entry point maps, module boundaries, and quickstart guides in background tasks.
- 🛡️ **Immediate Delete UI Cancellation**: Clicking "Delete" immediately stops status polling, aborts in-flight HTTP requests, clears local state, and suppresses 404 delete errors.
- 🔄 **SPA Reload Resiliency**: Synchronous bootstrap route guard in `main.tsx` detects browser reloads on `/chat`, wipes local session storage, redirects to `/`, and creates a brand-new session on the home page.

---

## System Architecture Overview

```mermaid
sequenceDiagram
    autonumber
    actor User as User Browser (React 19)
    participant API as FastAPI Backend
    participant Worker as Background Task / ThreadPool
    participant Extractor as Git / ZIP Extractor
    participant AST as Tree-sitter Parser
    participant Embed as OpenAI Embeddings API
    participant DB as Supabase PostgreSQL (pgvector)
    participant LLM as OpenRouter LLM

    User->>API: POST /api/sessions
    API-->>User: 201 Created (session_id, expires_at)

    User->>API: POST /api/ingest/github {repo_url}
    API->>Worker: Dispatch Ingestion Pipeline (Background Task)
    API-->>User: 202 Accepted {project_id, status: "queued"}

    loop Status Polling (GET /api/ingest/status/{project_id})
        User->>API: GET /api/ingest/status/{project_id}
        API-->>User: {status: "cloning"|"parsing"|"generating embeddings"|"saving", progress: %}
    end

    Worker->>Extractor: Clone depth=1 to /data/repos/{project_id}
    Worker->>AST: Parse AST Nodes & Comments into Chunks
    Worker->>Embed: Embed Chunks in Batches of 100 (1536-dim)
    Embed-->>Worker: Return Vector Array [1536]
    Worker->>DB: Store Projects, Files, Chunks (pgvector)
    Worker->>Extractor: DELETE Local Directory /data/repos/{project_id} (CLEANUP)
    Worker->>Worker: Spawn Phase 2 Intelligence Generation Task

    User->>API: GET /api/ingest/status/{project_id}
    API-->>User: {status: "completed", percentage: 100.0}

    User->>API: POST /api/query {project_id, question}
    API->>Embed: Embed User Query (1536-dim)
    API->>DB: Hybrid Search (pgvector Cosine Sim + PostgreSQL FTS)
    DB-->>API: Return Top Ranked Code Chunks
    API->>LLM: Prompt with Retrieved Context & Code Coordinates
    LLM-->>API: Response with File & Line Citations
    API-->>User: 200 OK {answer, sources}
```

---

## Technology Stack

| Layer | Technology | Version / Specification | Purpose |
|---|---|---|---|
| **Frontend UI** | React | 19.2.7 | Interactive UI framework |
| **Language** | TypeScript | 6.0.2 | End-to-end static typing |
| **Build System** | Vite | 8.1.1 | High-speed ESM bundling & dev server |
| **Styling** | TailwindCSS | 4.3.3 | Utility-first dark-mode styling |
| **Routing** | React Router DOM | 7.11.0 | Client-side SPA navigation |
| **HTTP Client** | Axios | 1.18.1 | Backend API requests with `X-Session-ID` header |
| **Backend API** | FastAPI | 0.111.0 | Asynchronous Python REST API framework |
| **ASGI Server** | Uvicorn | 0.30.1 | High-concurrency event-loop web server |
| **AST Parser** | Tree-sitter | 0.21.3 | Syntax tree parsing and structural symbol extraction |
| **Git Engine** | GitPython | 3.1.43 | Shallow repository cloning (`depth=1`) |
| **Embedding Engine** | OpenAI API | `text-embedding-3-small` (1536-dim) | Lightweight vector embedding API |
| **Database** | PostgreSQL | Supabase Hosted | Persistent session, project, chunk, and vector storage |
| **Vector Engine** | pgvector | 0.2.5 | HNSW cosine similarity vector index (`vector_cosine_ops`) |
| **LLM Provider** | OpenRouter API | `qwen/qwen3-30b-a3b:free` + fallbacks | Cited technical synthesis & question answering |
| **Backend Hosting** | Render | Python 3.11 Environment | Containerized cloud backend hosting |
| **Frontend Hosting** | Vercel | SPA Rewrites enabled | Global CDN frontend hosting |

---

## Database & Vector Storage Architecture

PostgreSQL running on Supabase with the `pgvector` extension provides vector search capabilities alongside relational session management.

### Database Tables Schema Summary

```sql
-- 1. Anonymous Ephemeral Sessions
CREATE TABLE IF NOT EXISTS sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- 2. Project Metadata
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    repo_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'queued',
    files_processed INTEGER DEFAULT 0,
    total_files INTEGER DEFAULT 0,
    current_file TEXT DEFAULT '',
    error TEXT
);

-- 3. File Map Table
CREATE TABLE IF NOT EXISTS files (
    id SERIAL PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    language TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    file_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Code Chunks with 1536-Dimensional pgvector Embedding
CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    language TEXT NOT NULL,
    symbol_name TEXT,
    symbol_type TEXT,
    parent_class TEXT,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536),
    chunking_method TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    fts_vector TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

-- HNSW Vector Cosine Index for Fast Nearest Neighbor Search
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
-- Full-Text Search GIN Index
CREATE INDEX IF NOT EXISTS chunks_fts_idx ON chunks USING gin(fts_vector);

-- 5. Chat History Table
CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Phase 2 Intelligence Cache Table
CREATE TABLE IF NOT EXISTS intelligence_cache (
    project_id UUID PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    summary_md TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Retrieval-Augmented Generation (RAG) Pipeline

GitSense AI implements a **Hybrid Search Pipeline** combining dense vector similarity with sparse keyword full-text matching:

1. **Query Intent Classification**:
   - `GENERAL_CODE`: Queries seeking specific code implementation details.
   - `ARCHITECTURE_OVERVIEW`: Queries asking for high-level repository summaries (serves cached Phase 2 overview).
   - `FILE_SPECIFIC`: Queries targeting explicit files.
   - `QUICKSTART_SETUP`: Setup and developer guide queries.

2. **Query Embedding**:
   - Generates a 1536-dimensional float vector for the user prompt using `text-embedding-3-small`.

3. **Hybrid PostgreSQL Candidate Fetching**:
   - **Semantic Search**: Fetches top 20 candidates using vector cosine distance:
     ```sql
     SELECT id, file_path, content, (1 - (embedding <=> %s::vector)) as similarity
     FROM chunks WHERE project_id = %s
     ORDER BY embedding <=> %s::vector LIMIT 20;
     ```
   - **Lexical Search**: Fetches top 20 candidates using PostgreSQL full-text search:
     ```sql
     SELECT id, file_path, content, ts_rank_cd(fts_vector, websearch_to_tsquery('english', %s)) as rank
     FROM chunks WHERE project_id = %s AND fts_vector @@ websearch_to_tsquery('english', %s)
     ORDER BY rank DESC LIMIT 20;
     ```

4. **Reciprocal Rank Fusion (RRF)**:
   - Combines vector and keyword candidates into a unified rank score:
     $$RRF\_Score(d) = \frac{1}{60 + rank_{semantic}(d)} + \frac{1}{60 + rank_{lexical}(d)}$$

5. **Prompt Injection & Cited Synthesis**:
   - Top reranked chunks are formatted with explicit line range headers (`[File: path/to/file.py, Lines 12-45]`) and injected into the LLM system prompt.

---

## AI / LLM Synthesis Architecture

- **Provider**: OpenRouter API (`https://openrouter.ai/api/v1`).
- **Primary Model**: `qwen/qwen3-30b-a3b:free`.
- **Fallback Models**:
  - `openrouter/free`
  - `cohere/north-mini-code:free`
  - `openai/gpt-oss-20b:free`
- **System Prompt Rules**:
  - Requires executive summary introduction.
  - Mandatory source citations with exact file paths and line ranges.
  - Strict refusal to speculate beyond provided context chunks.

---

## Repository Ingestion Lifecycle

```text
[User Ingestion Request]
        │
        ▼
1. Validation & Database Project Creation (status: "queued")
        │
        ▼
2. Shallow Clone / ZIP Extraction (`depth=1` to ./data/repos/<project_id>/)
        │
        ▼
3. File Audit & Filtering (skips binary, lock files, node_modules, .git)
        │
        ▼
4. AST Syntax Parsing (Tree-sitter extracts functions, classes, comments)
        │
        ▼
5. Batch Embedding Generation (OpenAI API, 100 chunks per request)
        │
        ▼
6. Vector Database Persistence (INSERT INTO chunks with VECTOR(1536))
        │
        ▼
7. Local File System Clean-Up (rmtree ./data/repos/<project_id>/)
        │
        ▼
8. Status Set to "completed" (percentage = 100%)
        │
        ▼
9. Detached Background Phase 2 Intelligence Summary Generation
```

---

## Query & Chat Workflow

1. User types question in `ChatPage.tsx`.
2. Request dispatched via `POST /api/query` with `X-Session-ID` header.
3. Backend classifies intent and embeds query via OpenAI API.
4. pgvector performs hybrid vector/FTS search and merges RRF scores.
5. Top code chunks formatted into prompt with coordinates.
6. OpenRouter LLM returns formatted answer with markdown source references.
7. Frontend renders response with interactive source citation drawer.

---

## Session & Project Lifecycles

- **Session Duration**: 3 hours (`SESSION_TIMEOUT_HOURS=3`).
- **Session Auto-Cleanup**: Server runs a background thread every 10 minutes checking `expires_at < NOW()`. Expired sessions trigger `CASCADE` deletion across `projects`, `files`, `chunks`, `chat_history`, and `intelligence_cache`.
- **One Repository Scope**: Sessions are anonymous, lightweight, and isolated.

---

## Immediate Delete & Cleanup Lifecycle

When the user clicks "Delete" on a project:
1. **Immediate Synchronous UI Stop**: Local React state (`setProjects`, `setIngestionProjectId(null)`, `setIsIngesting(false)`) updates **instantly** without waiting for the network API response.
2. **Poller Cancellation**: Polling interval `clearInterval()` runs and inflight status HTTP requests are cancelled via `AbortController`.
3. **Background API Execution**: `DELETE /api/projects/{project_id}` runs in the background.
4. **404 Error Suppression**: If backend returns `404 Not Found` (project already removed), it is treated as a successful cleanup without error toasts.
5. **Clean Workspace Reload**: Sidebar and workspace reload cleanly, ready for a new repository.

---

## Browser Refresh & SPA Routing Behavior

- **Vercel SPA Rewrites (`vercel.json`)**: Configured with `"source": "/(.*)", "destination": "/index.html"`, preventing Vercel from returning `404 NOT_FOUND` HTML pages on `/chat` reloads.
- **Bootstrap Route Guard (`main.tsx`)**: Executes synchronously in `main.tsx` **before** `createRoot().render()`.
  - If a browser reload is detected on `/chat` (or direct unauthenticated access to `/chat`):
    1. Synchronously wipes local session storage (`clearSessionState()`).
    2. Updates URL to `/` using `window.history.replaceState(null, '', '/')`.
    3. Mounts React app on `/` and requests a **brand-new session**. `ChatPage` is **never rendered**.
- **Normal SPA Navigation**: Clicking "Get Started" or submitting a repo navigates `/` -> `/chat` via React Router DOM without triggering redirects.

---

## API Endpoints Overview

| Method | Endpoint Path | Description |
|---|---|---|
| `POST` | `/api/sessions` | Create a new 3-hour anonymous session |
| `POST` | `/api/ingest/github` | Ingest public GitHub repository URL |
| `POST` | `/api/ingest/zip` | Upload and ingest codebase ZIP archive |
| `GET` | `/api/ingest/status/{project_id}` | Poll repository ingestion status & percentage |
| `POST` | `/api/query` | Submit natural language query against project |
| `GET` | `/api/projects` | List all projects belonging to active session |
| `GET` | `/api/projects/{project_id}/files` | Retrieve flat file tree map for project |
| `GET` | `/api/projects/{project_id}/chat` | Fetch chat interaction history for project |
| `DELETE` | `/api/projects/{project_id}` | Delete project and all associated database records |
| `GET` | `/api/projects/{project_id}/export/pdf` | Export full RAG project report as PDF |
| `GET` | `/api/system/health` | Health check endpoint returning status `ok` |

---

## Frontend-Backend Communication

- **Protocol**: HTTP/REST over JSON.
- **Header Authentication**: `X-Session-ID: <session_uuid>` header appended dynamically via Axios request interceptor (`api.ts`).
- **Timeouts**:
  - Session creation: 15 seconds
  - Standard REST calls: 60 seconds
  - ZIP File Uploads: 120 seconds

---

## Environment Configuration

### Backend Environment Variables (`backend/.env`)

```env
# OpenRouter API Key & LLM Configuration
OPENROUTER_API_KEY=sk-or-v1-your-openrouter-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=qwen/qwen3-30b-a3b:free
LLM_FALLBACK_MODELS=["openrouter/free","cohere/north-mini-code:free","openai/gpt-oss-20b:free"]

# External Embedding API Config (Lightweight API-based Embeddings)
OPENAI_API_KEY=sk-your-openai-api-key-here
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536

# Supabase Auth & PostgreSQL Database Credentials
SUPABASE_URL=https://your-supabase-project.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key_here
DATABASE_URL=postgresql://postgres.your-project-id:your_db_password@aws-0-region.pooler.supabase.com:5432/postgres

# Backend Internal Settings
UPLOAD_DIR=./data/uploads
REPO_DIR=./data/repos
RESET_DATABASE_ON_START=false
SESSION_TIMEOUT_HOURS=3
CLEANUP_INTERVAL_MINUTES=10
```

### Frontend Environment Variables (`frontend/.env`)

```env
# Base API URL pointing to FastAPI Backend server
VITE_API_BASE_URL=http://localhost:8000

# Optional EmailJS Credentials (Contact Modal)
VITE_EMAILJS_SERVICE_ID=your_emailjs_service_id
VITE_EMAILJS_TEMPLATE_ID=your_emailjs_template_id
VITE_EMAILJS_PUBLIC_KEY=your_emailjs_public_key
```

---

## Local Development Setup

### Prerequisites
- **Python**: 3.11.x
- **Node.js**: 18.x or higher
- **PostgreSQL Database**: Supabase account or local PostgreSQL with `pgvector` extension enabled.

### 1. Backend Setup

```bash
# Navigate to backend folder
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Copy environment template and configure settings
cp .env.example .env

# Run FastAPI backend development server
python run.py
```
Backend will start on `http://localhost:8000` (API documentation available at `http://localhost:8000/docs`).

### 2. Frontend Setup

```bash
# Navigate to frontend folder
cd frontend

# Install frontend dependencies
npm install

# Copy environment template
cp .env.example .env

# Start Vite development server
npm run dev
```
Frontend will start on `http://localhost:5173`.

---

## Production Cloud Deployment

### Backend Deployment (Render)
1. Environment: **Python 3.11**.
2. Build Command: `pip install -r requirements.txt`.
3. Start Command: `python run.py` (or `uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
4. Set Environment Variables (`OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `DATABASE_URL`, `SUPABASE_URL`, etc.) in Render Dashboard.

### Frontend Deployment (Vercel)
1. Framework Preset: **Vite**.
2. Root Directory: `frontend` (or project root).
3. Build Command: `npm run build`.
4. Output Directory: `dist`.
5. Set `VITE_API_BASE_URL` to your production backend URL (e.g. `https://gitsenseai-xxwq.onrender.com`).
6. Ensure `vercel.json` SPA rewrites file is included.

---

## Project Directory Structure

```text
GitSense_Ai/
├── .env.example
├── sample.env
├── vercel.json
├── README.md
├── EMBEDDING_DEPLOYMENT_OPTIMIZATION.md
├── RELOAD_FIX_REPORT.md
├── SESSION_AND_DELETE_LIFECYCLE_FIX.md
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── run.py
│   ├── README.md
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   │   ├── dependencies.py
│   │   │   ├── routes_ingest.py
│   │   │   ├── routes_projects.py
│   │   │   ├── routes_query.py
│   │   │   ├── routes_sessions.py
│   │   │   └── routes_system.py
│   │   ├── core/
│   │   │   ├── chunker.py
│   │   │   ├── embedder.py
│   │   │   ├── extractor.py
│   │   │   ├── intelligence_engine.py
│   │   │   ├── llm.py
│   │   │   ├── query_classifier.py
│   │   │   ├── rag_pipeline.py
│   │   │   └── vectorstore.py
│   │   ├── db/
│   │   │   ├── schema.sql
│   │   │   └── supabase.py
│   │   ├── models/
│   │   │   └── schemas.py
│   │   └── utils/
│   │       ├── file_cleanup.py
│   │       ├── file_filters.py
│   │       ├── language_map.py
│   │       └── text_sanitizer.py
│   └── tests/
│       ├── test_api_embeddings.py
│       ├── test_nonblocking_ingestion.py
│       └── test_temporary_storage.py
└── frontend/
    ├── package.json
    ├── vercel.json
    ├── vite.config.ts
    ├── index.html
    ├── README.md
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── utils/
        │   └── session.ts
        ├── context/
        │   └── AppContext.tsx
        ├── services/
        │   └── api.ts
        ├── pages/
        │   ├── LandingPage.tsx
        │   └── ChatPage.tsx
        ├── components/
        │   ├── layout/
        │   │   ├── Navbar.tsx
        │   │   └── ContactModal.tsx
        │   └── ui/
        │       ├── Accordion.tsx
        │       ├── Button.tsx
        │       ├── MarkdownRenderer.tsx
        │       └── Modal.tsx
        └── types/
            └── index.ts
```

---

## Security & Ephemeral Resource Isolation

1. **No Long-Term Code Retention**: Cloned repository folders are deleted immediately after indexing.
2. **Anonymous Session Keys**: No user credentials, accounts, or personal data stored.
3. **Database Cascade Auto-Deletion**: Expired 3-hour session rows purge all associated projects, file trees, chunks, and vector embeddings automatically.
4. **Environment Secret Protection**: Secret keys (`OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `DATABASE_URL`) are read purely server-side and never sent to the browser client.

---

## Error Handling & Resiliency

- **HTTP Status Codes**:
  - `400 Bad Request`: Invalid GitHub URLs or unparseable archive payloads.
  - `404 Not Found`: Requesting a non-existent project or deleted session resource.
  - `409 Conflict`: Attempting to launch parallel ingestion for a project currently indexing.
  - `410 Gone`: Explicitly signals server-side session expiration to trigger client session re-creation.
  - `422 Unprocessable Entity`: Schema validation errors.
  - `500 Internal Error`: Handled with exception trace logging and user-friendly error details.
- **Tenacity Exponential Backoff**: OpenAI API calls auto-retry up to 3 attempts with exponential delay (1s to 10s).

---

## Performance Optimization & Low-Memory Footprint

- **RAM Consumption**: Purged heavy local ML dependencies (`torch`, `sentence-transformers`, `CUDA`). Runtime memory footprint stays **<50 MB RAM**.
- **Thread Pool Offloading**: Offloaded heavy CPU/IO disk operations (file discovery, Tree-sitter AST parsing, text hashing) to worker threads via `asyncio.to_thread`.
- **HNSW Indexing**: Uses HNSW vector cosine similarity indexes in pgvector for sub-10ms candidate retrieval.
- **Dynamic API Batching**: Embeds text chunks in slices of 100 items per API call.

---

## Known Limitations

- **Public GitHub Repositories Only**: Private repositories require supplying access tokens via HTTP headers.
- **Supported AST Languages**: Full AST structural node extraction is supported for 10 languages (Python, JS, TS, Go, Rust, Java, C, C++, PHP, Ruby). Other plain text formats fallback to windowed fallback chunking.

---

## Future Enhancements

- [ ] Private GitHub Repository OAuth authentication integration.
- [ ] Multi-repository cross-codebase similarity comparison.
- [ ] Automated pull request architectural review assistant.
- [ ] Local Ollama / Llama.cpp fallback engine for offline air-gapped environments.
