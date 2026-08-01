from pathlib import Path

# Directories to strictly ignore during ingestion
IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "target",
    "out",
    "venv",
    ".venv",
    "__pycache__",
    ".idea",
    ".vscode",
    ".settings"
}

# Supported file extensions for indexing
SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml"
}

# Binary file extensions to strictly ignore/skip
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svgz", ".pdf", ".zip", ".gz", ".7z", ".rar",
    ".exe", ".dll", ".so", ".bin", ".class", ".jar", ".woff", ".woff2", ".ttf", ".otf",
    ".mp3", ".mp4", ".avi", ".mov", ".wasm"
}


def should_index_file(file_path: Path) -> bool:
    """
    Checks if a file should be indexed based on its name, extension, 
    and whether it is located inside an ignored directory.
    """
    suffix = file_path.suffix.lower()
    
    # Skip binary files
    if suffix in BINARY_EXTENSIONS:
        return False

    # Check extension
    if suffix not in SUPPORTED_EXTENSIONS:
        return False

    # Check if any parent directories are in the ignore list
    for part in file_path.parts:
        if part in IGNORED_DIRECTORIES:
            return False

    return True


def is_ignored_directory(dir_name: str) -> bool:
    """
    Checks if a directory name is in the ignore list.
    """
    return dir_name in IGNORED_DIRECTORIES
