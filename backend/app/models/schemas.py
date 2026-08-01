from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl, UUID4


# Session Schemas
class SessionResponse(BaseModel):
    """
    Response schema containing details of the created anonymous session.
    """
    session_id: UUID4
    created_at: datetime
    expires_at: datetime


# Ingestion Schemas
class GithubIngestRequest(BaseModel):
    """
    Request payload for cloning and indexing a GitHub repository.
    """
    repo_url: HttpUrl = Field(..., description="The HTTPS URL of the GitHub repository to clone.")


class IngestStatusResponse(BaseModel):
    """
    Status of the repository ingestion process.
    """
    project_id: UUID4
    status: str = Field(..., description="Status: queued | processing | completed | failed")
    files_processed: int = Field(0, description="Number of files successfully parsed and indexed.")
    total_files: int = Field(0, description="Total files discovered in the repository.")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


# Query Schemas
class QueryRequest(BaseModel):
    """
    Payload for asking questions about a project.
    """
    project_id: UUID4
    question: str = Field(..., min_length=3, description="The natural language question to ask the LLM.")


class SourceCitation(BaseModel):
    """
    Citation metadata for retrieved source code sections used in answers.
    """
    file_path: str
    start_line: int
    end_line: int
    snippet: str


class QueryResponse(BaseModel):
    """
    Q&A response containing the generated answer and verified source code citations.
    """
    answer: str
    sources: List[SourceCitation]


# Project Schemas
class ProjectMetadata(BaseModel):
    """
    General summary of a project in the database.
    """
    project_id: UUID4
    project_name: str
    language_summary: Dict[str, int] = Field(
        default_factory=dict, 
        description="Breakdown of languages used, mapped to the count of files using them."
    )
    file_count: int
    ingestion_date: datetime
    status: str


class FileEntry(BaseModel):
    """
    A single file entry within a project's tree.
    """
    file_path: str
    language: str
    size_bytes: int


class FileTreeResponse(BaseModel):
    """
    Response containing the complete flat or structured file list of a project.
    """
    project_id: UUID4
    files: List[FileEntry]


class ChatHistoryEntry(BaseModel):
    """
    An entry in the project Q&A chat history.
    """
    id: int
    question: str
    answer: str
    sources: List[SourceCitation]
    created_at: datetime
