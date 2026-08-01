import axios from 'axios';
import {
  SessionResponse,
  GithubIngestRequest,
  IngestStatusResponse,
  QueryRequest,
  QueryResponse,
  ProjectMetadata,
  FileTreeResponse,
  ChatHistoryEntry
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 60s timeout for large uploads/network latency
});

// Request interceptor to dynamically append the current session ID
apiClient.interceptors.request.use((config) => {
  const sessionId = localStorage.getItem('gitsense_session_id');
  if (sessionId) {
    config.headers['X-Session-ID'] = sessionId;
  }
  return config;
});

// Central API endpoints implementation
export const apiService = {
  // Session Endpoints
  async createSession(): Promise<SessionResponse> {
    const response = await apiClient.post<SessionResponse>('/api/sessions');
    return response.data;
  },

  // Ingestion Endpoints
  async ingestGithub(payload: GithubIngestRequest): Promise<{ project_id: string; status: string; message: string }> {
    const response = await apiClient.post<{ project_id: string; status: string; message: string }>('/api/ingest/github', payload);
    return response.data;
  },

  async ingestZip(file: File): Promise<{ project_id: string; status: string; message: string }> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post<{ project_id: string; status: string; message: string }>('/api/ingest/zip', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 120000, // 120s for ZIP uploads
    });
    return response.data;
  },

  async getIngestionStatus(projectId: string): Promise<IngestStatusResponse> {
    const response = await apiClient.get<IngestStatusResponse>(`/api/ingest/status/${projectId}`);
    return response.data;
  },

  // Query Endpoints
  async queryProject(payload: QueryRequest): Promise<QueryResponse> {
    const response = await apiClient.post<QueryResponse>('/api/query', payload);
    return response.data;
  },

  // Project Endpoints
  async listProjects(): Promise<ProjectMetadata[]> {
    const response = await apiClient.get<ProjectMetadata[]>('/api/projects');
    return response.data;
  },

  async deleteProject(projectId: string): Promise<{ project_id: string; status: string; message: string }> {
    const response = await apiClient.delete<{ project_id: string; status: string; message: string }>(`/api/projects/${projectId}`);
    return response.data;
  },

  async getProjectFiles(projectId: string): Promise<FileTreeResponse> {
    const response = await apiClient.get<FileTreeResponse>(`/api/projects/${projectId}/files`);
    return response.data;
  },

  async getChatHistory(projectId: string): Promise<ChatHistoryEntry[]> {
    const response = await apiClient.get<ChatHistoryEntry[]>(`/api/projects/${projectId}/chat`);
    return response.data;
  },

  getExportPdfUrl(projectId: string): string {
    const sessionId = localStorage.getItem('gitsense_session_id') || '';
    return `${API_BASE_URL}/api/projects/${projectId}/export/pdf?session_id=${sessionId}`;
  }
};
