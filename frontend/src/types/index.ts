export interface SessionResponse {
  session_id: string;
  created_at: string;
  expires_at: string;
}

export interface GithubIngestRequest {
  repo_url: string;
}

export interface IngestStatusResponse {
  project_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  files_processed: number;
  total_files: number;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

export interface SourceCitation {
  file_path: string;
  start_line: number;
  end_line: number;
  snippet: string;
}

export interface QueryRequest {
  project_id: string;
  question: string;
}

export interface QueryResponse {
  answer: string;
  sources: SourceCitation[];
}

export interface ProjectMetadata {
  project_id: string;
  project_name: string;
  language_summary: Record<string, number>;
  file_count: number;
  ingestion_date: string;
  status: string;
}

export interface FileEntry {
  file_path: string;
  language: string;
  size_bytes: number;
}

export interface FileTreeResponse {
  project_id: string;
  files: FileEntry[];
}

export interface ChatHistoryEntry {
  id: number;
  question: string;
  answer: string;
  sources: SourceCitation[];
  created_at: string;
}

export interface ContactFormData {
  name: string;
  email: string;
  message: string;
}
