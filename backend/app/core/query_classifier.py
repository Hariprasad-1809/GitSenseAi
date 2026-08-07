import re
from typing import Dict, Any

# Intent Category Constants
INTENT_ARCHITECTURE = "ARCHITECTURE"
INTENT_REPOSITORY_SUMMARY = "REPOSITORY_SUMMARY"
INTENT_WORKFLOW = "WORKFLOW"
INTENT_API = "API"
INTENT_DATABASE = "DATABASE"
INTENT_CONFIGURATION = "CONFIGURATION"
INTENT_DEPLOYMENT = "DEPLOYMENT"
INTENT_AUTHENTICATION = "AUTHENTICATION"
INTENT_CODE_EXPLANATION = "CODE_EXPLANATION"
INTENT_BUG_FIXING = "BUG_FIXING"
INTENT_PERFORMANCE = "PERFORMANCE"
INTENT_GENERAL_CODE = "GENERAL_CODE"


def classify_query(query: str) -> Dict[str, Any]:
    """
    Classifies a user query into specific intent categories to optimize
    retrieval strategy, cache key selection, and prompt engineering.
    """
    q = query.lower().strip()
    
    # 1. Repository Summary / High-level Overview
    summary_keywords = [
        "summarize this repository", "summarize this project", "summarize the repository",
        "summarize the project", "explain this project", "explain this repository",
        "what does this project do", "what does this repository do", "what is this project about",
        "what is this repository about", "repository summary", "project summary", "codebase summary"
    ]
    if any(kw in q for kw in summary_keywords):
        return {
            "intent": INTENT_REPOSITORY_SUMMARY,
            "cache_key": "repo_summary",
            "requires_summary": True,
            "system_prompt_type": "summary"
        }

    # 2. Architecture & High-level Layout
    arch_keywords = [
        "architecture", "architectural", "backbone", "main backbone", "codebase layout", "project structure",
        "folder structure", "folder responsibilities", "design pattern", "system design", "component layout",
        "how is the project organized", "how is the code structured", "module breakdown", "tech stack",
        "how frontend communicates", "frontend to backend", "communication flow"
    ]
    if any(kw in q for kw in arch_keywords):
        return {
            "intent": INTENT_ARCHITECTURE,
            "cache_key": "architecture_summary",
            "requires_summary": True,
            "system_prompt_type": "architecture"
        }

    # 3. Workflows & Execution Flow
    workflow_keywords = [
        "workflow", "execution flow", "request flow", "request lifecycle", "lifecycle", "call graph",
        "pipeline", "how does data flow", "data flow", "step by step", "process flow", "sequence",
        "entry points", "entrypoint", "execution graph"
    ]
    if any(kw in q for kw in workflow_keywords):
        return {
            "intent": INTENT_WORKFLOW,
            "cache_key": "workflow_summary",
            "requires_summary": True,
            "system_prompt_type": "workflow"
        }

    # 4. API Endpoints & Routes
    api_keywords = [
        "api", "endpoint", "route", "http", "controller", "rest",
        "get /", "post /", "delete /", "put /", "fastapi route", "router"
    ]
    if any(kw in q for kw in api_keywords):
        return {
            "intent": INTENT_API,
            "cache_key": "api_summary",
            "requires_summary": False,
            "system_prompt_type": "api"
        }

    # 5. Database & Schema
    db_keywords = [
        "database", "schema", "table", "sql", "migration", "pgvector",
        "postgres", "supabase", "foreign key", "model", "orm"
    ]
    if any(kw in q for kw in db_keywords):
        return {
            "intent": INTENT_DATABASE,
            "cache_key": "database_summary",
            "requires_summary": False,
            "system_prompt_type": "database"
        }

    # 6. Configuration & Setup
    config_keywords = [
        "config", "configuration", "environment", "env", "requirements.txt",
        "package.json", "setup", "install", "build", "run the project", "how to start"
    ]
    if any(kw in q for kw in config_keywords):
        return {
            "intent": INTENT_CONFIGURATION,
            "cache_key": "tech_stack",
            "requires_summary": False,
            "system_prompt_type": "config"
        }

    # 7. Authentication & Security
    auth_keywords = ["auth", "authentication", "session", "jwt", "token", "permission", "security"]
    if any(kw in q for kw in auth_keywords):
        return {
            "intent": INTENT_AUTHENTICATION,
            "cache_key": None,
            "requires_summary": False,
            "system_prompt_type": "code"
        }

    # 8. Bug Fixing / Exception Handling
    bug_keywords = ["error", "bug", "exception", "failed", "crash", "fix", "issue"]
    if any(kw in q for kw in bug_keywords):
        return {
            "intent": INTENT_BUG_FIXING,
            "cache_key": None,
            "requires_summary": False,
            "system_prompt_type": "code"
        }

    # 9. Performance & Optimization
    perf_keywords = ["performance", "speed", "latency", "benchmark", "optimize", "slow", "bottleneck"]
    if any(kw in q for kw in perf_keywords):
        return {
            "intent": INTENT_PERFORMANCE,
            "cache_key": None,
            "requires_summary": False,
            "system_prompt_type": "code"
        }

    # 10. Default General Code Query
    return {
        "intent": INTENT_GENERAL_CODE,
        "cache_key": None,
        "requires_summary": False,
        "system_prompt_type": "code"
    }
