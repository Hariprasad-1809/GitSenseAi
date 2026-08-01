# GitSense AI Backend API Details

This document outlines the API endpoints required for the GitSense AI backend, their input/output schemas, and the files where they are implemented.

---

## 1. Ingestion API (`app/api/routes_ingest.py`)

Handles uploading and repository ingestion processes.

### 1.1 Upload ZIP File
- **Endpoint**: `POST /api/ingest/zip`
- **Request Type**: Multipart Form
- **Form Data**:
  - `file`: Uploaded `.zip` file.
- **Response**: `202 Accepted`
  ```json
  {
    "project_id": "uuid-string-here",
    "status": "queued",
    "message": "ZIP upload accepted. Ingestion processing has started in the background."
  }
  ```

### 1.2 Ingest GitHub Repository
- **Endpoint**: `POST /api/ingest/github`
- **Request Body** (`application/json`):
  ```json
  {
    "repo_url": "https://github.com/username/repo-name"
  }
  ```
- **Response**: `202 Accepted`
  ```json
  {
    "project_id": "uuid-string-here",
    "status": "queued",
    "message": "GitHub repository cloning and ingestion started in the background."
  }
  ```

### 1.3 Ingestion Status
- **Endpoint**: `GET /api/ingest/status/{project_id}`
- **Response**: `200 OK`
  ```json
  {
    "project_id": "uuid-string-here",
    "status": "queued|processing|completed|failed",
    "files_processed": 0,
    "total_files": 0,
    "started_at": "2026-07-19T12:00:00Z",
    "completed_at": null,
    "error": null
  }
  ```

---

## 2. Query/Q&A API (`app/api/routes_query.py`)

Handles interactive questions against ingested code projects.

### 2.1 Ask a Question
- **Endpoint**: `POST /api/query`
- **Request Body** (`application/json`):
  ```json
  {
    "project_id": "uuid-string-here",
    "question": "Explain how authentication works in this repository."
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "answer": "Explanation of authentication...",
    "sources": [
      {
        "file_path": "app/core/auth.py",
        "start_line": 25,
        "end_line": 63,
        "snippet": "def verify_token(token: str)..."
      }
    ]
  }
  ```

### 2.2 Get Chat History
- **Endpoint**: `GET /api/projects/{project_id}/chat`
- **Response**: `200 OK`
  ```json
  [
    {
      "id": 1,
      "question": "Explain how authentication works...",
      "answer": "...",
      "sources": [...],
      "created_at": "2026-07-19T12:05:00Z"
    }
  ]
  ```

---

## 3. Project Management API (`app/api/routes_projects.py`)

Handles metadata overview, deletion, and tree views of ingested projects.

### 3.1 List Projects
- **Endpoint**: `GET /api/projects`
- **Response**: `200 OK`
  ```json
  [
    {
      "project_id": "uuid-string-here",
      "project_name": "My Project",
      "language_summary": {
        "Python": 25,
        "JavaScript": 12
      },
      "file_count": 37,
      "ingestion_date": "2026-07-19T12:00:00Z",
      "status": "completed"
    }
  ]
  ```

### 3.2 Delete Project
- **Endpoint**: `DELETE /api/projects/{project_id}`
- **Response**: `200 OK`
  ```json
  {
    "project_id": "uuid-string-here",
    "status": "deleted",
    "message": "Project folder and all database items have been removed."
  }
  ```

### 3.3 Get File Tree
- **Endpoint**: `GET /api/projects/{project_id}/files`
- **Response**: `200 OK`
  Returns the hierarchy of the codebase.
  ```json
  {
    "project_id": "uuid-string-here",
    "files": [
      {
        "file_path": "app/main.py",
        "language": "python",
        "size_bytes": 1024
      }
    ]
  }
  ```

---

## Files to Update / Create

All file routes and business logic files are specified below:
- **`app/main.py`**: Initializes the FastAPI app, manages CORS, and mounts routers.
- **`app/api/routes_ingest.py`**: Handles ingest endpoints, starts background processing.
- **`app/api/routes_query.py`**: Handles queries, invokes the RAG pipeline.
- **`app/api/routes_projects.py`**: Lists/deletes projects and serves file trees.
- **`app/core/rag_pipeline.py`**: Orchestrates indexing (ingesting, parsing, embedding, saving) and query resolution.
- **`app/core/vectorstore.py`**: Executes direct SQL against PostgreSQL for hybrid search and DB insertions.
