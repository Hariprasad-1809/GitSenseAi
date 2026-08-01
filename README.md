# GitSense AI

## AI-Powered GitHub Repository Analysis & Chat Assistant

GitSense AI is a Retrieval-Augmented Generation (RAG) application that enables developers to understand, explore, and interact with GitHub repositories using natural language. Instead of manually searching through files, users can ask questions about a codebase and receive context-aware answers generated from the repository itself.

The system clones a GitHub repository, parses its source code, intelligently chunks the content, generates vector embeddings, and stores them in PostgreSQL with pgvector. During querying, GitSense AI retrieves the most relevant code snippets and documentation before using Google's Gemini model to generate accurate, repository-specific responses.

---

## Features

* Analyze public GitHub repositories.
* AI-powered repository chat using RAG.
* Automatic repository cloning and indexing.
* Semantic code search using vector embeddings.
* Repository-specific answers with source references.
* Session-based architecture without user authentication.
* Export chat history as PDF.
* Background repository indexing.
* Markdown and syntax-highlighted responses.
* RESTful FastAPI backend.
* Modern React frontend with responsive UI.

---

## How It Works

1. Create a temporary session.
2. Submit a GitHub repository URL.
3. Clone the repository.
4. Parse source files.
5. Chunk code intelligently.
6. Generate embeddings.
7. Store embeddings in PostgreSQL (pgvector).
8. Retrieve relevant chunks for each query.
9. Generate an AI response using Gemini.
10. Export conversations as PDF if required.

---

## Tech Stack

### Frontend

* React
* TypeScript
* Vite
* Tailwind CSS
* shadcn/ui
* Framer Motion
* React Router
* Axios
* React Hook Form
* Zod
* Lucide Icons
* React Markdown

### Backend

* Python
* FastAPI
* LangChain
* Tree-sitter
* Sentence Transformers (BAAI/bge-small-en-v1.5)
* Google Gemini API
* PostgreSQL
* pgvector
* Psycopg 3
* GitPython
* ReportLab

### Database

* Supabase PostgreSQL
* pgvector

---

## Architecture

```text
Frontend
      │
      ▼
FastAPI Backend
      │
      ├── Session Management
      ├── Repository Cloning
      ├── Tree-sitter Parsing
      ├── Code Chunking
      ├── Embedding Generation
      ├── Vector Search
      ├── Gemini LLM
      └── PDF Export
             │
             ▼
      PostgreSQL + pgvector
```

---

## API Workflow

```text
Create Session
      │
      ▼
Repository Ingestion
      │
      ▼
Index Repository
      │
      ▼
Ask Questions
      │
      ▼
Retrieve Relevant Chunks
      │
      ▼
Gemini Generates Answer
      │
      ▼
Export Chat as PDF
```

---

## Use Cases

* Understand unfamiliar codebases quickly.
* Onboard new developers faster.
* Explore open-source repositories.
* Analyze project architecture.
* Explain functions, classes, and modules.
* Search code semantically.
* Generate repository documentation.

---

## Future Improvements

* Multi-repository support.
* Repository comparison.
* Codebase visualization.
* Conversation history.
* Role-based authentication.
* Support for private repositories.
* Advanced reranking for improved retrieval.
* Streaming AI responses.
* Multi-language repository support.

---

## License

This project is intended for educational, research, and software engineering purposes.
