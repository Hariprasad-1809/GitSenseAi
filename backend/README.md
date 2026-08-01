# GitSense AI - Backend RAG Engine

GitSense AI is a production-quality Retrieval-Augmented Generation (RAG) backend that enables developers to understand, explore, and analyze software repositories using natural language. 

Users can upload a ZIP archive of their codebase or provide a public GitHub URL. The backend automatically extracts files, parses syntax trees using Tree-sitter, computes vector embeddings locally, stores them in PostgreSQL using pgvector, and resolves user queries with OpenRouter LLMs (defaulting to Qwen3 30B) using precise source-level citations.

---

## Project Architecture

```
gitsense-backend/
├── app/
│   ├── main.py                 # FastAPI Application entry point, lifespans, CORS & middlewares
│   ├── config.py               # Pydantic Settings configuration (env parsing)
│   ├── api/
│   │   ├── routes_ingest.py    # Codebase ingestion (ZIP upload & GitHub Cloner)
│   │   ├── routes_query.py     # Q&A interactive queries and chat history
│   │   └── routes_projects.py  # Project listings, deletions, and file tree lookups
│   ├── core/
│   │   ├── extractor.py        # Clones Git repos and extracts ZIP files
│   │   ├── chunker.py          # Syntax-aware AST parsing, markdown and fallback chunkers
│   │   ├── embedder.py         # Local SentenceTransformers (bge-small-en-v1.5) loader
│   │   ├── vectorstore.py      # PostgreSQL direct psycopg vector insertions & hybrid queries
│   │   ├── llm.py              # OpenRouter API connector using the OpenAI SDK
│   │   └── rag_pipeline.py     # RAG indexing & Q&A orchestrator
│   ├── db/
│   │   ├── supabase.py         # DB connection manager and init migrations
│   │   └── schema.sql          # SQL schema migrations (pgvector, tables, indexes)
│   ├── models/
│   │   └── schemas.py          # Pydantic schemas for requests and responses
│   └── utils/
│       ├── file_filters.py     # Ignore directories and supported extension lists
│       └── language_map.py     # Mapping file extensions to Tree-sitter targets
├── requirements.txt            # Pinned dependencies
├── .env.example                # Configuration template
└── README.md                   # This instruction file
```

---

## Workflow Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant API as FastAPI Ingestion Route
    participant Worker as Background Task
    participant TS as Tree-sitter Parser
    participant BGE as Local SentenceTransformers
    participant DB as Supabase PostgreSQL (pgvector)
    participant LLM as OpenRouter LLM

    Dev->>API: POST /api/ingest/github {repo_url}
    API-->>Dev: Return HTTP 202 Accepted (queued/project_id)
    API->>Worker: Dispatch Ingestion Task
    Worker->>Worker: Shallow Clone (depth=1)
    
    loop For each supported file
        Worker->>TS: Parse AST (Classes, Methods, Functions)
        TS-->>Worker: AST Symbol nodes + Preceding Comments
        Worker->>BGE: Generate Embeddings locally (bge-small-en-v1.5)
        BGE-->>Worker: 384-dimensional float arrays
        Worker->>DB: Batch Insert chunks + embeddings + FTS vector
    end
    Worker->>DB: Update Project Status to 'completed'

    Dev->>API: POST /api/query {project_id, question}
    API->>BGE: Generate query embedding
    BGE-->>API: Query Vector
    API->>DB: Cosine Similarity search (Top 8)
    API->>DB: PostgreSQL Full-Text Search (Top 8)
    API->>API: Reciprocal Rank Fusion (RRF) -> Top 5
    API->>LLM: Send Context (Headed by files & lines) + Strict Prompt
    LLM-->>API: Answer text with precise citations
    API->>DB: Save Q&A Turn to chat_history
    API-->>Dev: Return Answer & Citation Sources
```

---

## Getting Started

### 1. Prerequisites
- Python 3.11+ (Python 3.12 recommended)
- Git (must be installed on the host to allow GitPython cloning)
- PostgreSQL database with `pgvector` enabled (such as Supabase)

### 2. Installation & Setup

You can choose to install dependencies globally/system-wide (the workspace default configuration) or use a Python virtual environment.

#### Option A: System Python (Recommended / Workspace Default)
To configure the project to use your system Python directly:
1. Ensure the virtual environment folder (`.venv` or `venv`) is deleted from the project directory.
2. Install all required dependencies from `requirements.txt` into the system Python:
   ```bash
   python -m pip install -r requirements.txt
   ```
3. To configure your editor/IDE to use system Python, ensure the workspace settings (e.g. `.vscode/settings.json`) point to your system Python interpreter:
   ```json
   {
     "python.defaultInterpreterPath": "C:\\Program Files\\Python312\\python.exe"
   }
   ```

#### Option B: Virtual Environment (Alternative)
1. Navigate to the `backend` directory and create a virtual environment:
   ```bash
   # Create virtual environment
   python -m venv .venv
   ```
2. Activate the virtual environment:
   - **On Windows (PowerShell)**: `.venv\Scripts\Activate.ps1`
   - **On Linux / macOS**: `source .venv/bin/activate`
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### 3. Environment Variables Setup
Create a `.env` file at the root of the `backend` workspace (copied from `.env.example`):

```bash
cp .env.example .env
```

Fill in the required environment variables:
- `OPENROUTER_API_KEY`: Obtain this from OpenRouter.
- `OPENROUTER_BASE_URL`: Base URL for OpenRouter (default: `https://openrouter.ai/api/v1`).
- `LLM_MODEL`: Active model to query (default: `qwen/qwen3-30b-a3b:free`). You can switch to any other model supported by OpenRouter (e.g., `meta-llama/llama-3-8b-instruct:free`, `google/gemini-2.5-flash`) by modifying this value.
- `LLM_FALLBACK_MODELS`: List of fallback model identifiers (e.g. `["openrouter/free", "cohere/north-mini-code:free"]`) to attempt at request runtime if the active model is unavailable (HTTP 404) or deprecated (HTTP 410). Successful fallback dynamically updates the active model to bypass repeating the sequence on future calls. Transient issues (such as 429 rate limits, 500/502/503 status codes, or network timeouts) are raised immediately without fallback.
- `SUPABASE_URL` & `SUPABASE_ANON_KEY` & `SUPABASE_SERVICE_ROLE_KEY`: Fetch these from your Supabase Project API Settings.
- `DATABASE_URL`: Direct PostgreSQL connection URL. E.g., `postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres`

### 4. Database Setup & pgvector Configuration
Before launching the application, ensure the `vector` extension is enabled on your PostgreSQL database. If you use Supabase, this is pre-installed. The backend automatically initializes tables and indexes on startup by executing `app/db/schema.sql`.

To verify or enable extensions manually, execute:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

---

## Running the Backend

Start the FastAPI backend server. On Windows, it is highly recommended to run the launcher script `run.py` (or `python app/main.py`) directly. This ensures the correct event loop policy (`WindowsSelectorEventLoopPolicy`) is configured before starting Uvicorn, which is required by `psycopg` for async connections:

```bash
python run.py
```

Alternatively, on non-Windows systems, you can also run through `python -m uvicorn`:

```bash
python -m uvicorn app.main:app --reload --reload-exclude data --host 127.0.0.1 --port 8000
```


Once running, you can explore the Interactive Swagger Documentation at:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## API Documentation & Curl Requests

### 1. Ingest a GitHub Repository
Accepts a public GitHub HTTPS URL, clones the repository shallowly, processes/chunks code files, generates embeddings locally, and saves them into the DB.

- **Request**:
```bash
curl -X POST "http://127.0.0.1:8000/api/ingest/github" \
     -H "Content-Type: application/json" \
     -d '{"repo_url": "https://github.com/fastapi/fastapi"}'
```
- **Response** (HTTP 202):
```json
{
  "project_id": "c1a011de-3e3e-4fb4-b8bb-c20fe1d29bfb",
  "status": "queued",
  "message": "GitHub repository request received. Cloning has been scheduled in the background."
}
```

### 2. Ingest a ZIP Code Archive
Accepts multipart files and processes them in the background.

- **Request**:
```bash
curl -X POST "http://127.0.0.1:8000/api/ingest/zip" \
     -F "file=@/path/to/your/project.zip"
```

### 3. Check Ingestion Status
Retrieve processing status and file logs.

- **Request**:
```bash
curl -X GET "http://127.0.0.1:8000/api/ingest/status/c1a011de-3e3e-4fb4-b8bb-c20fe1d29bfb"
```

### 4. Query Project (Standard Q&A Mode)
Answers developer queries using RRF hybrid search and OpenRouter LLM.

- **Request**:
```bash
curl -X POST "http://127.0.0.1:8000/api/query" \
     -H "Content-Type: application/json" \
     -d '{"project_id": "c1a011de-3e3e-4fb4-b8bb-c20fe1d29bfb", "question": "Where is the FastAPI app initialized?"}'
```
- **Response**:
```json
{
  "answer": "The FastAPI application is initialized in `fastapi/applications.py` between lines 105 and 150 where the class `FastAPI` is constructed with arguments...",
  "sources": [
    {
      "file_path": "fastapi/applications.py",
      "start_line": 105,
      "end_line": 150,
      "snippet": "class FastAPI(Starlette):\n    def __init__(self, ...)"
    }
  ]
}
```

### 5. Query Project (Summary Mode)
Intent is automatically detected. If a user asks "Explain this project" or "Summarize the architecture", GitSense AI retrieves core representative chunks (README, main configs, directory headers) and outputs a detailed architectural overview.

- **Request**:
```bash
curl -X POST "http://127.0.0.1:8000/api/query" \
     -H "Content-Type: application/json" \
     -d '{"project_id": "c1a011de-3e3e-4fb4-b8bb-c20fe1d29bfb", "question": "Summarize this repository and describe the architecture."}'
```

### 6. List Indexed Projects
Returns list of all projects indexed, their main languages, and sizes.

- **Request**:
```bash
curl -X GET "http://127.0.0.1:8000/api/projects"
```

### 7. Fetch Project Code File Tree
Retrieves a flat list of all parsed files with file size.

- **Request**:
```bash
curl -X GET "http://127.0.0.1:8000/api/projects/c1a011de-3e3e-4fb4-b8bb-c20fe1d29bfb/files"
```

### 8. Delete a Project
Cleans up database tables (projects, files, chunks, chat history) and deletes local storage repositories.
Uses a robust deletion routine that handles Windows file locks and permission issues on `.git/objects/pack/` indices by closing GitPython repository handles, releasing memory references, and modifying file permissions dynamically.

- **Request**:
```bash
curl -X DELETE "http://127.0.0.1:8000/api/projects/c1a011de-3e3e-4fb4-b8bb-c20fe1d29bfb"
```
