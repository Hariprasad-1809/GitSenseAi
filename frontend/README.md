# GitSense AI - React/Vite Frontend Explorer

This is the complete production-ready frontend interface for **GitSense AI**, a codebase retrieval-augmented generation (RAG) platform. It provides a visual interface for shallow-cloning/extracting projects, polling parsing state, exploring flat file structures, and asking natural language questions with inline citations.

---

## 1. Tech Stack

- **Framework**: React 19 + Vite + TypeScript (Strict Mode)
- **Styling**: Tailwind CSS v4 (native compiler plugins)
- **State Management**: React Context (`AppProvider`)
- **Routing**: React Router DOM v6
- **Validation**: React Hook Form + Zod resolvers
- **Networking**: Axios Client (auto-injecting headers)
- **Animation**: Framer Motion
- **Toasts**: Sonner

---

## 2. Project Folder Structure

```
frontend/
├── dist/                        # Production compiled bundle output
├── public/                      # Static assets (favicons, icons)
├── src/
│   ├── App.tsx                  # Main router entry configuration
│   ├── main.tsx                 # Bootstrapper index
│   ├── index.css                # Tailwind CSS imports & theme configurations
│   ├── types/
│   │   └── index.ts             # TypeScript definitions matching backend Pydantic models
│   ├── services/
│   │   ├── api.ts               # Central Axios client (intercepts and appends X-Session-ID)
│   │   └── emailjs.ts           # EmailJS email dispatcher wrapper
│   ├── context/
│   │   └── AppContext.tsx       # Global state coordinator (Session, projects, file logs)
│   ├── components/
│   │   ├── ui/                  # Composables and shared components
│   │   │   ├── Button.tsx       # Loading & variant styles button
│   │   │   ├── Modal.tsx        # Accessibility-conscious Dialog wrapper
│   │   │   ├── Accordion.tsx    # FAQ collapse-expand item list
│   │   │   └── MarkdownRenderer.tsx # Text syntax formatter with code block copy actions
│   │   └── layout/
│   │       ├── Navbar.tsx       # Glassmorphic global navigation banner
│   │       └── ContactModal.tsx # Contact us validator forms linked to EmailJS
│   └── pages/
│       ├── LandingPage.tsx      # Premium SaaS intro landing page
│       └── ChatPage.tsx         # ChatGPT-like codebase dialog explorer
├── .env                         # Local environment variables
├── .env.example                 # Variables configurations template
├── package.json                 # Project scripts and dependencies
├── tsconfig.json                # TS configurations index
├── tsconfig.app.json            # Strict TypeScript compiler options
└── vite.config.ts               # Vite server configurations + Tailwind v4 + path aliases
```

---

## 3. Folders & Core Components Purpose

- **types/**: Houses strict typing declarations representing Pydantic schemas defined in the backend.
- **services/**:
  - `api.ts`: Pre-configured Axios instance. Automatically adds the active session token `X-Session-ID` to all requests.
  - `emailjs.ts`: Email service encapsulating contact form message dispatching.
- **context/**:
  - `AppContext.tsx`: Handles session token creation, project lists retrieval, active project indexing state, flat file tree listings, and lazy session recovery.
- **components/ui/**:
  - `Button`: Accessibility-friendly UI button handling loading spinners.
  - `Modal`: Transition animations, Esc-key closures, and focus-locking container.
  - `Accordion`: Framer motion animated height collapsible dropdown.
  - `MarkdownRenderer`: A lightweight parser built for React 19 that formats text paragraphs, list hierarchies, and maps syntax code segments with clipboard copy functions.
- **components/layout/**:
  - `Navbar`: Global glassmorphic link navigation panel.
  - `ContactModal`: Handles zod validations and triggers email sends.
- **pages/**:
  - `LandingPage`: SaaS landing experience with scroll-triggered animations.
  - `ChatPage`: ChatGPT-like workspace. Integrates cloning form triggers, live progress indicators, file trees, messaging turns, inline citation clicks, and PDF export lookups.

---

## 4. Routing Setup

Configured in `src/App.tsx` using `react-router-dom`:
- **`/`**: Displays the `LandingPage` containing feature descriptions, project introductions, FAQ lists, and contact forms.
- **`/chat`**: Displays the interactive `ChatPage` for importing, indexing, and querying repositories.

---

## 5. State Management Approach

Uses a React Context provider (`AppProvider` in `src/context/AppContext.tsx`) to coordinate state globally. It stores and shares:
- The active `sessionId`.
- List of `projects` indexed.
- The `currentProject` metadata.
- The current project's `fileTree`.
- The active conversation `chatHistory`.
- Loading indicators (`isLoadingProjects`, `isLoadingFiles`, `isLoadingChat`).
- Ingestion state indicators (`isIngesting`, `ingestionProjectId`).

It also manages the initialization and lazy restoration of session tokens. If the backend returns `410 Session Expired`, the state manager handles the error, resets local storage, and initializes a new session.

---

## 6. Backend Integration Endpoints

The frontend integrates with the existing FastAPI backend using the following endpoints:
1. **`POST /api/sessions`**: Instantiates a new anonymous session.
2. **`POST /api/ingest/github`**: Sends repository HTTPS URL payload to initiate background shallow cloning and AST parsing.
3. **`POST /api/ingest/zip`**: Uploads code ZIP archive using multipart form data.
4. **`GET /api/ingest/status/{project_id}`**: Polls background indexing progress, counts, and errors.
5. **`POST /api/query`**: Resolves user queries using vector embeddings and hybrid search.
6. **`GET /api/projects`**: Lists all projects indexed under the current session.
7. **`DELETE /api/projects/{project_id}`**: Deletes project files and database tables.
8. **`GET /api/projects/{project_id}/files`**: Retrieves flat file listings.
9. **`GET /api/projects/{project_id}/chat`**: Loads previous conversation logs.
10. **`GET /api/projects/{project_id}/export/pdf`**: Streams conversation logs as a PDF.

---

## 7. EmailJS Integration

The Contact Us form is integrated with EmailJS:
- Form fields are validated with React Hook Form and Zod (`contactSchema` in `src/components/layout/ContactModal.tsx`).
- Submissions trigger `emailService.sendContactMessage` in `src/services/emailjs.ts`, which calls `emailjs.send`.
- Secrets (service ID, template ID, public key) are read from environment variables.

---

## 8. Run & Setup Guide

### 1. Prerequisites
- **Node.js**: v18.0.0 or higher (v20+ recommended)
- **NPM**: v9.0.0 or higher
- Running GitSense AI FastAPI backend (defaulting to `http://localhost:8000`)

### 2. Environment Setup
Create a `.env` file in the `frontend` folder (copied from `.env.example`):
```bash
cp .env.example .env
```
Fill in the configuration details:
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_EMAILJS_SERVICE_ID=your_service_id
VITE_EMAILJS_TEMPLATE_ID=your_template_id
VITE_EMAILJS_PUBLIC_KEY=your_public_key
```

### 3. Installation Commands
Install dependencies:
```bash
npm install
```

### 4. Running the Dev Server
Start the frontend development server:
```bash
npm run dev
```
The server starts at `http://localhost:5173`.

### 5. Production Compilation
Build the production bundle:
```bash
npm run build
```
Generates optimized static assets in the `dist` directory.

### 6. Previewing Build
To preview the compiled production app locally:
```bash
npm run preview
```
