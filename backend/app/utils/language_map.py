from typing import Dict, Optional

# Maps extensions to Tree-sitter language identifiers used by tree-sitter-languages
# If an extension is not present or has None, it indicates Tree-sitter parser is not used.
EXTENSION_TO_TREESITTER = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php"
}

# Maps extensions to human-readable names for UI summaries
EXTENSION_TO_DISPLAY_NAME = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript (React)",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".java": "Java",
    ".c": "C",
    ".h": "C/C++ Header",
    ".cpp": "C++",
    ".hpp": "C++ Header",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".sh": "Shell",
    ".bash": "Shell",
    ".css": "CSS",
    ".html": "HTML",
    ".sql": "SQL",
    ".md": "Markdown",
    ".txt": "Plain Text",
    ".json": "JSON Config",
    ".yaml": "YAML Config",
    ".yml": "YAML Config",
    ".toml": "TOML Config",
    ".xml": "XML Config"
}


def get_treesitter_language(extension: str) -> Optional[str]:
    """
    Returns the Tree-sitter language identifier for a given file extension,
    or None if the extension doesn't support or require Tree-sitter parsing.
    """
    return EXTENSION_TO_TREESITTER.get(extension.lower())


def get_display_name(extension: str) -> str:
    """
    Returns a human-readable display name for the language/file type.
    Defaults to 'Unknown'.
    """
    return EXTENSION_TO_DISPLAY_NAME.get(extension.lower(), "Unknown")
