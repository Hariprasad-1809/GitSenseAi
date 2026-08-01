import logging
import uuid
import io
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from fastapi.concurrency import run_in_threadpool
from app.config import settings
from app.core.extractor import cleanup_project_files
from app.core.vectorstore import delete_project, get_project_files, get_project_status, list_projects, get_chat_history
from app.models.schemas import FileEntry, FileTreeResponse, ProjectMetadata
from app.api.dependencies import get_active_session_id, validate_project_session

# ReportLab imports for PDF Generation
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["Projects"])


import html
import re


def markdown_to_reportlab_html(text: str) -> str:
    """
    Converts basic markdown syntax to ReportLab Paragraph-compatible XML tags.
    Ensures safe escaping of special characters.
    """
    if not text:
        return ""
    # 1. Escape HTML entities first to prevent XML parsing crashes
    escaped = html.escape(text, quote=True)
    
    # 2. Convert code blocks: ```lang ... ``` -> Courier font wrap with background
    def repl_code_block(match):
        code_content = match.group(1)
        return f'<br/><font name="Courier" size="8.5" color="#0F172A" backColor="#F8FAFC">{code_content}</font><br/>'
    
    escaped = re.sub(r'```(?:[a-zA-Z0-9+#-]+)?\n(.*?)\n```', repl_code_block, escaped, flags=re.DOTALL)
    
    # 3. Convert bold: **text** -> <b>text</b>
    escaped = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', escaped)
    # 4. Convert italic: *text* -> <i>text</i>
    escaped = re.sub(r'\*(.*?)\*', r'<i>\1</i>', escaped)
    # 5. Convert inline code: `code` -> Courier font wrap
    escaped = re.sub(r'`(.*?)`', r'<font name="Courier" size="9" color="#0F172A" backColor="#F1F5F9">\1</font>', escaped)
    
    # 6. Replace newlines with <br/>
    escaped = escaped.replace('\n', '<br/>')
    return escaped


def generate_pdf_buffer(project_name: str | None, repo_url: str | None, history: List[dict]) -> io.BytesIO:
    """
    Generates a PDF using reportlab containing the chat history and project metadata.
    Returns the file contents in an in-memory BytesIO buffer.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styling
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=colors.HexColor('#1E293B'), # Slate-800
        spaceAfter=15
    )
    
    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#64748B'), # Slate-500
        spaceAfter=25
    )
    
    question_style = ParagraphStyle(
        'Question',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        textColor=colors.HexColor('#2563EB'), # Blue-600
        spaceBefore=10,
        spaceAfter=4
    )
    
    answer_style = ParagraphStyle(
        'Answer',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#334155'), # Slate-700
        spaceAfter=15
    )
    
    timestamp_style = ParagraphStyle(
        'Timestamp',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        textColor=colors.HexColor('#94A3B8'), # Slate-400
        spaceAfter=10
    )
    
    story = []
    
    # Title Header
    story.append(Paragraph("GitSense AI - Conversation Export", title_style))
    
    # Session / Project Meta info
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    project_name_safe = html.escape(project_name or "Unknown Project")
    meta_info = f"<b>Repository Name:</b> {project_name_safe}<br/>"
    if repo_url:
        repo_url_safe = html.escape(repo_url)
        meta_info += f"<b>Repository URL:</b> <font color='#2563EB'>{repo_url_safe}</font><br/>"
    meta_info += f"<b>Generated Timestamp:</b> {now_str}"
    
    story.append(Paragraph(meta_info, meta_style))
    story.append(Spacer(1, 10))
    
    # Conversation log
    if not history:
        story.append(Paragraph("No conversation history found for this session.", answer_style))
    else:
        for idx, chat in enumerate(history, 1):
            created_at = chat.get("created_at")
            if isinstance(created_at, datetime):
                time_str = created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            else:
                time_str = str(created_at)
                
            q_text_safe = markdown_to_reportlab_html(chat.get('question', ''))
            q_paragraph = Paragraph(f"<b>Q{idx}: {q_text_safe}</b>", question_style)
            time_paragraph = Paragraph(f"Asked at: {time_str}", timestamp_style)
            
            # Format answers safely
            ans_text_safe = markdown_to_reportlab_html(chat.get('answer', ''))
            a_paragraph = Paragraph(ans_text_safe, answer_style)
            
            # Group each Q&A together so they don't break across pages where avoidable
            story.append(KeepTogether([q_paragraph, time_paragraph, a_paragraph, Spacer(1, 8)]))
            
    doc.build(story)
    buffer.seek(0)
    return buffer


@router.get("", response_model=List[ProjectMetadata])
async def get_all_projects(session_id: uuid.UUID = Depends(get_active_session_id)):
    """
    Retrieves metadata summaries for all projects indexed in the system for this session.
    """
    try:
        projects = await list_projects(session_id)
        return projects
    except Exception as e:
        logger.error(f"Failed to list projects: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while listing projects: {e}"
        )


@router.delete("/{project_id}", status_code=status.HTTP_200_OK)
async def remove_project(
    project_id: uuid.UUID = Depends(validate_project_session),
    session_id: uuid.UUID = Depends(get_active_session_id)
):
    """
    Deletes a project, removing all physical repositories, database metadata, embeddings, and chat histories.
    """
    try:
        # Delete database rows (Cascades delete files, chunks, chat history)
        db_deleted = await delete_project(project_id)
        
        # Clean up physical code folder asynchronously
        await run_in_threadpool(cleanup_project_files, str(project_id))
        logger.info(f"Repository deleted: project_id={project_id} (session_id={session_id})")
        
        if not db_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete project database entries."
            )
            
        return {
            "project_id": str(project_id),
            "status": "deleted",
            "message": "Project folder and all database items have been successfully removed."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting the project: {e}"
        )


@router.get("/{project_id}/files", response_model=FileTreeResponse)
async def get_project_file_tree(
    project_id: uuid.UUID = Depends(validate_project_session)
):
    """
    Returns a complete flat listing of files indexed in a project with their size in bytes.
    """
    try:
        # Retrieve files from db
        db_files = await get_project_files(project_id)
        
        # Calculate file sizes from the file system
        file_entries = []
        for file in db_files:
            file_path = file["file_path"]
            abs_path = settings.repo_path / str(project_id) / file_path
            
            size_bytes = 0
            if abs_path.is_file():
                try:
                    size_bytes = abs_path.stat().st_size
                except Exception:
                    size_bytes = 0
                    
            file_entries.append(
                FileEntry(
                    file_path=file_path,
                    language=file["language"],
                    size_bytes=size_bytes
                )
            )
            
        return FileTreeResponse(
            project_id=project_id,
            files=file_entries
        )
    except Exception as e:
        logger.error(f"Failed to fetch file tree for project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching the file tree: {e}"
        )


@router.get("/{project_id}/export/pdf")
async def export_chat_pdf(
    project_id: uuid.UUID = Depends(validate_project_session),
    session_id: uuid.UUID = Depends(get_active_session_id)
):
    """
    Generates and returns a downloadable PDF conversation log of the active session's queries and answers.
    """
    try:
        # Fetch project status for repository name/URL info
        proj_status = await get_project_status(project_id)
        if not proj_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )

        # Retrieve chat history
        history = await get_chat_history(project_id)
        
        logger.info(f"PDF export started: project_id={project_id} (session_id={session_id})")
        
        pdf_buffer = generate_pdf_buffer(
            project_name=proj_status["project_name"],
            repo_url=proj_status.get("repo_url"),
            history=history
        )
        
        # Format download filename based on repository/project name and export date
        repo_name = proj_status.get("project_name") or "project"
        sanitized_name = repo_name.replace(" ", "_")
        sanitized_name = re.sub(r'[^a-zA-Z0-9\-_]', '', sanitized_name)
        sanitized_name = sanitized_name or "project"
        export_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        download_filename = f"GitSense_{sanitized_name}_{export_date}.pdf"
        
        headers = {
            'Content-Disposition': f'attachment; filename="{download_filename}"'
        }
        return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export PDF for project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while generating PDF: {e}"
        )
