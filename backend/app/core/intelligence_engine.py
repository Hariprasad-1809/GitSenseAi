import logging
import uuid
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.config import settings
from app.db.supabase import get_cached_intelligence, save_cached_intelligence
from app.core.llm import call_gemini_async
from app.utils.file_filters import should_index_file

logger = logging.getLogger(__name__)


def build_lightweight_repo_map(repo_path: Path) -> Dict[str, Any]:
    """
    Builds a lightweight structural map of the repository during file discovery.
    Categorizes file tree, folder responsibilities, languages, entry points, APIs, services, and models.
    """
    file_tree = []
    folders = set()
    languages = {}
    entry_points = []
    key_configs = []
    routes = []
    services = []
    models = []
    
    for p in repo_path.rglob("*"):
        if p.is_file() and should_index_file(p):
            rel = str(p.relative_to(repo_path)).replace("\\", "/")
            ext = p.suffix.lower().replace(".", "") or "plain"
            file_tree.append(rel)
            languages[ext] = languages.get(ext, 0) + 1
            
            # Directory grouping
            parts = rel.split("/")
            if len(parts) > 1:
                folders.add(parts[0])
                if len(parts) > 2:
                    folders.add(f"{parts[0]}/{parts[1]}")
            
            # Categorize key files
            filename = p.name.lower()
            if filename in ("main.py", "app.py", "index.js", "index.ts", "server.js", "main.go", "main.rs", "run.py"):
                entry_points.append(rel)
            elif filename in ("package.json", "requirements.txt", "pyproject.toml", "dockerfile", "docker-compose.yml", "schema.sql"):
                key_configs.append(rel)
            elif "route" in filename or "api" in filename:
                routes.append(rel)
            elif "service" in filename:
                services.append(rel)
            elif "model" in filename or "schema" in filename:
                models.append(rel)
                
    return {
        "file_count": len(file_tree),
        "folder_list": sorted(list(folders)),
        "languages": languages,
        "entry_points": entry_points,
        "key_configs": key_configs,
        "routes": routes[:15],
        "services": services[:15],
        "models": models[:15],
        "sample_file_tree": file_tree[:150]
    }


async def generate_repository_summary(project_id: uuid.UUID, project_name: str, repo_map: Dict[str, Any], context_samples: str) -> str:
    """
    Generates a structured Repository Overview summary.
    """
    system_prompt = (
        "You are GitSense AI, a principal software architect assistant.\n"
        "Your task is to analyze the provided repository metadata and context snippets to generate a high-level Repository Summary.\n"
        "Structure the response clearly:\n"
        "1. Executive Summary (Purpose of the codebase)\n"
        "2. Core Functionality & Features\n"
        "3. Technology Stack & Frameworks\n"
        "4. Primary Entry Points & Module Boundaries\n"
        "5. Developer Quickstart Guide\n\n"
        "Cite real file paths mentioned in the context."
    )
    user_prompt = (
        f"Project Name: {project_name}\n"
        f"Repository Map Stats:\n{json.dumps(repo_map, indent=2)}\n\n"
        f"Context Samples:\n{context_samples}\n\n"
        "Provide a comprehensive Repository Summary:"
    )
    try:
        summary = await call_gemini_async(system_prompt, user_prompt)
        return summary.strip()
    except Exception as e:
        logger.error(f"Failed to generate repository summary for {project_id}: {e}")
        return f"# Project Summary: {project_name}\n\nThis repository contains {repo_map.get('file_count', 0)} files across languages: {list(repo_map.get('languages', {}).keys())}."


async def generate_architecture_summary(project_id: uuid.UUID, project_name: str, repo_map: Dict[str, Any], context_samples: str) -> str:
    """
    Generates an Architecture Breakdown & Backbone summary.
    """
    system_prompt = (
        "You are GitSense AI, a principal software architect assistant.\n"
        "Analyze the repository structure and context to describe the system architecture.\n"
        "Structure the response clearly:\n"
        "1. Executive Summary (System Backbone & Design Philosophy)\n"
        "2. Folder Structure & Folder Responsibilities\n"
        "3. Core Subsystems & Module Boundaries\n"
        "4. Execution Flow & Request Lifecycle\n"
        "5. API & Data Layer Interaction\n"
        "6. Technology Stack & Framework Choices\n"
        "7. Key File Paths & Component Maps\n\n"
        "Cite real file paths in code references."
    )
    user_prompt = (
        f"Project Name: {project_name}\n"
        f"Repo Map:\n{json.dumps(repo_map, indent=2)}\n\n"
        f"Context Samples:\n{context_samples}\n\n"
        "Provide a detailed System Architecture & Backbone Summary:"
    )
    try:
        summary = await call_gemini_async(system_prompt, user_prompt)
        return summary.strip()
    except Exception as e:
        logger.error(f"Failed to generate architecture summary for {project_id}: {e}")
        return f"# Architecture Summary: {project_name}\n\nCore entry points: {repo_map.get('entry_points', [])}."


async def generate_workflow_summary(project_id: uuid.UUID, project_name: str, repo_map: Dict[str, Any], context_samples: str) -> str:
    """
    Generates a Workflow & Execution Flow breakdown summary.
    """
    system_prompt = (
        "You are GitSense AI, a principal software architect assistant.\n"
        "Analyze the repository metadata and entry points to detail the system execution workflow.\n"
        "Structure the response clearly:\n"
        "1. Request Lifecycle Overview\n"
        "2. Step-by-Step Data Flow (Frontend to Backend to DB)\n"
        "3. Core Handlers & Service Intermediaries\n"
        "4. Async / Background Task Processing\n"
        "5. Output & Response Construction\n\n"
        "Cite real file paths and function names."
    )
    user_prompt = (
        f"Project Name: {project_name}\n"
        f"Repo Map Entry Points & Routes:\n{json.dumps({'entry_points': repo_map.get('entry_points', []), 'routes': repo_map.get('routes', []), 'services': repo_map.get('services', [])}, indent=2)}\n\n"
        f"Context Samples:\n{context_samples}\n\n"
        "Provide a detailed Execution Workflow Summary:"
    )
    try:
        summary = await call_gemini_async(system_prompt, user_prompt)
        return summary.strip()
    except Exception as e:
        logger.error(f"Failed to generate workflow summary for {project_id}: {e}")
        return f"# Workflow Summary: {project_name}\n\nExecution flow starts at entry points: {repo_map.get('entry_points', [])}."


async def run_background_intelligence_worker(project_id: uuid.UUID, project_name: str, repo_path: Path) -> None:
    """
    Phase 2 Asynchronous Worker Task.
    Executes AFTER Phase 1 indexing is completed and status is set to 'completed'.
    Generates advanced intelligence (repo summary, architecture breakdown, workflow flow)
    and caches them in the intelligence_cache database table.
    NEVER delays indexing completion or blocks the user.
    """
    logger.info(f"[PHASE 2 WORKER] Starting background intelligence generation for project '{project_name}' ({project_id})...")
    try:
        # Build lightweight repo map
        repo_map = await asyncio.to_thread(build_lightweight_repo_map, repo_path)
        
        # Read sample context files (READMEs, entry points, configs)
        sample_texts = []
        for rel_file in repo_map.get("key_configs", []) + repo_map.get("entry_points", []):
            full_p = repo_path / rel_file
            if full_p.exists() and full_p.is_file():
                try:
                    text = full_p.read_text(encoding="utf-8", errors="ignore")[:3000]
                    sample_texts.append(f"--- File: {rel_file} ---\n{text}")
                except Exception:
                    pass
                    
        # Check README.md
        readme_path = repo_path / "README.md"
        if readme_path.exists():
            try:
                readme_text = readme_path.read_text(encoding="utf-8", errors="ignore")[:4000]
                sample_texts.insert(0, f"--- File: README.md ---\n{readme_text}")
            except Exception:
                pass

        context_samples = "\n\n".join(sample_texts) if sample_texts else "No sample text files found."

        # 1. Generate & Cache Repository Summary
        repo_summary = await generate_repository_summary(project_id, project_name, repo_map, context_samples)
        await save_cached_intelligence(project_id, "repo_summary", repo_summary, {"type": "repo_summary"})
        logger.info(f"[PHASE 2 WORKER] Cached 'repo_summary' for project {project_id}.")

        # 2. Generate & Cache Architecture Summary
        arch_summary = await generate_architecture_summary(project_id, project_name, repo_map, context_samples)
        await save_cached_intelligence(project_id, "architecture_summary", arch_summary, {"type": "architecture_summary"})
        logger.info(f"[PHASE 2 WORKER] Cached 'architecture_summary' for project {project_id}.")

        # 3. Generate & Cache Workflow Summary
        workflow_summary = await generate_workflow_summary(project_id, project_name, repo_map, context_samples)
        await save_cached_intelligence(project_id, "workflow_summary", workflow_summary, {"type": "workflow_summary"})
        logger.info(f"[PHASE 2 WORKER] Cached 'workflow_summary' for project {project_id}.")

        # 4. Store Repo Map as Tech Stack intelligence
        await save_cached_intelligence(project_id, "tech_stack", json.dumps(repo_map), {"type": "repo_map"})

        logger.info(f"[PHASE 2 WORKER] Background intelligence worker completed successfully for project {project_id}.")

    except Exception as e:
        logger.error(f"[PHASE 2 WORKER] Background intelligence worker encountered an error for project {project_id}: {e}", exc_info=True)


async def get_or_generate_intelligence(
    project_id: uuid.UUID, 
    cache_key: str, 
    project_name: str, 
    repo_path: Optional[Path] = None
) -> str:
    """
    Smart Cache Lookup & Lazy Generation.
    Checks DB cache for precomputed intelligence. If missing, generates it on-demand lazily,
    saves it to the database, and returns it.
    """
    cached = await get_cached_intelligence(project_id, cache_key)
    if cached and cached.get("content"):
        logger.info(f"[SMART CACHE HIT] Retrieved '{cache_key}' from database for project {project_id}.")
        return cached["content"]

    logger.info(f"[SMART CACHE MISS] Generating '{cache_key}' on-demand lazily for project {project_id}...")
    
    # Lazy generation fallback
    if repo_path and repo_path.exists():
        repo_map = build_lightweight_repo_map(repo_path)
    else:
        repo_map = {"file_count": 0, "languages": {}}

    context_samples = f"Project: {project_name}"
    
    if cache_key == "architecture_summary":
        summary = await generate_architecture_summary(project_id, project_name, repo_map, context_samples)
    elif cache_key == "workflow_summary":
        summary = await generate_workflow_summary(project_id, project_name, repo_map, context_samples)
    else:
        summary = await generate_repository_summary(project_id, project_name, repo_map, context_samples)

    # Save to database cache for all future queries
    await save_cached_intelligence(project_id, cache_key, summary, {"generated": "lazily_on_demand"})
    return summary
