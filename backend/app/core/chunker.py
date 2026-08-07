import logging
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional
from tree_sitter_languages import get_parser
from app.utils.language_map import get_treesitter_language

logger = logging.getLogger(__name__)

_TS_PARSER_CACHE: Dict[str, Any] = {}


def compute_file_hash(content: str) -> str:
    """Computes SHA-256 hash of file content string for fast incremental indexing checks."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_cached_ts_parser(lang_name: str) -> Any:
    """Returns cached tree-sitter parser instance to avoid re-instantiation per file."""
    if lang_name not in _TS_PARSER_CACHE:
        _TS_PARSER_CACHE[lang_name] = get_parser(lang_name)
    return _TS_PARSER_CACHE[lang_name]


def count_tokens_heuristic(text: str) -> int:
    """
    Heuristically counts tokens by splitting on whitespace.
    1 word ≈ 1.3 tokens.
    """
    words = text.split()
    return int(len(words) * 1.3)


def fallback_chunker(text: str, token_limit: int = 500, overlap: int = 50) -> List[Dict[str, Any]]:
    """
    Splits text into chunks of at most token_limit tokens with overlap.
    It preserves line boundaries to keep code context logical.
    """
    lines = text.splitlines()
    chunks = []
    
    # Calculate heuristic tokens per line
    line_tokens = [max(1, count_tokens_heuristic(line)) for line in lines]
    
    start_idx = 0
    num_lines = len(lines)
    
    while start_idx < num_lines:
        current_tokens = 0
        end_idx = start_idx
        
        while end_idx < num_lines and current_tokens + line_tokens[end_idx] <= token_limit:
            current_tokens += line_tokens[end_idx]
            end_idx += 1
            
        if end_idx == start_idx:
            # If a single line is larger than token_limit, force include it
            end_idx += 1
            
        chunk_lines = lines[start_idx:end_idx]
        chunk_content = "\n".join(chunk_lines)
        
        chunks.append({
            "content": chunk_content,
            "start_line": start_idx + 1,
            "end_line": end_idx
        })
        
        # Calculate backtrack for overlap
        overlap_tokens = 0
        backtrack = 0
        for i in range(end_idx - 1, start_idx, -1):
            if overlap_tokens + line_tokens[i] > overlap:
                break
            overlap_tokens += line_tokens[i]
            backtrack += 1
            
        if backtrack == 0 or end_idx == num_lines:
            start_idx = end_idx
        else:
            start_idx = end_idx - backtrack
            
    return chunks


def chunk_markdown(text: str) -> List[Dict[str, Any]]:
    """
    Splits Markdown files by heading markers (# , ## , etc.).
    If no headings are present, falls back to 500-token chunks with 50-token overlap.
    """
    lines = text.splitlines()
    chunks = []
    
    current_chunk_lines = []
    start_line = 1
    has_headings = False
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('#') and len(stripped.split()[0]) <= 6:
            # We found a heading
            has_headings = True
            if current_chunk_lines:
                chunks.append({
                    "content": "\n".join(current_chunk_lines),
                    "start_line": start_line,
                    "end_line": i
                })
            current_chunk_lines = [line]
            start_line = i + 1
        else:
            current_chunk_lines.append(line)
            
    if current_chunk_lines:
        chunks.append({
            "content": "\n".join(current_chunk_lines),
            "start_line": start_line,
            "end_line": len(lines)
        })
        
    if not has_headings:
        # Fallback to standard chunker
        return fallback_chunker(text, token_limit=500, overlap=50)
        
    return chunks


def get_preceding_comments(lines: List[str], start_line_idx: int, language: str) -> str:
    """
    Scans backwards from a symbol's starting line to extract adjacent comment lines.
    """
    comment_lines = []
    idx = start_line_idx - 1
    empty_lines = 0
    
    while idx >= 0:
        line = lines[idx].strip()
        if not line:
            empty_lines += 1
            if empty_lines > 1:
                break
            idx -= 1
            continue
            
        is_comment = False
        if language == "python" and line.startswith("#"):
            is_comment = True
        elif language != "python" and (
            line.startswith("//") or 
            line.startswith("/*") or 
            line.startswith("*") or 
            line.endswith("*/")
        ):
            is_comment = True
            
        if is_comment:
            comment_lines.append(lines[idx])
            empty_lines = 0
            idx -= 1
        else:
            break
            
    if not comment_lines:
        return ""
        
    comment_lines.reverse()
    return "\n".join(comment_lines) + "\n"


def map_symbol_type(node_type: str) -> Optional[str]:
    """
    Maps AST node type names to generic symbol categories.
    """
    if "class" in node_type or node_type == "class_specifier":
        return "class"
    if node_type == "struct_specifier":
        return "struct"
    if "interface" in node_type:
        return "interface"
    if "constructor" in node_type:
        return "constructor"
    if "method" in node_type or node_type == "method_definition":
        return "method"
    if "function" in node_type:
        return "function"
    return None


def get_symbol_name(node: Any, source_bytes: bytes) -> str:
    """
    Extracts the name of the symbol from the AST node.
    """
    # 1. Look for children that represent identifiers
    for child in node.children:
        if child.type in ("identifier", "type_identifier", "property_identifier"):
            return source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="ignore")
            
    # 2. Specialize for C/C++ function declarators
    if node.type == "function_definition":
        declarator = node.child_by_field_name("declarator")
        if declarator:
            return find_identifier_in_node(declarator, source_bytes) or "anonymous_function"
            
    # 3. Fallback to 'name' field
    name_node = node.child_by_field_name("name")
    if name_node:
        return source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="ignore")
        
    return "anonymous"


def find_identifier_in_node(node: Any, source_bytes: bytes) -> Optional[str]:
    """
    Deep search for the first identifier in a node. Useful for nested C/C++ declarators.
    """
    if node.type in ("identifier", "type_identifier", "property_identifier"):
        return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
    for child in node.children:
        res = find_identifier_in_node(child, source_bytes)
        if res:
            return res
    return None


def traverse_ast(node: Any, source_bytes: bytes, parent_class: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Recursively walks the AST to find classes, methods, functions, constructors, and interfaces.
    """
    symbols = []
    symbol_type = map_symbol_type(node.type)
    current_parent = parent_class
    
    if symbol_type:
        name = get_symbol_name(node, source_bytes)
        # Tree-sitter points are 0-indexed for lines, we convert to 1-indexed
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        content = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
        
        # Override function type to method if nested in class
        if symbol_type == "function" and parent_class:
            symbol_type = "method"
            
        symbols.append({
            "symbol_name": name,
            "symbol_type": symbol_type,
            "parent_class": parent_class,
            "start_line": start_line,
            "end_line": end_line,
            "content": content
        })
        
        if symbol_type == "class":
            current_parent = name
            
    for child in node.children:
        symbols.extend(traverse_ast(child, source_bytes, current_parent))
        
    return symbols


def extract_file_metadata(content: str, file_path: str, extension: str) -> Dict[str, Any]:
    """
    Extracts high-level file metadata such as module scope, imports, and framework detection.
    """
    import re
    parts = file_path.split("/")
    module_name = parts[0] if len(parts) > 1 else "root"
    
    imports = []
    framework = "plain"
    ext_lower = extension.lower()
    
    # Lightweight regex for imports and framework detection
    if "python" in ext_lower or ext_lower == ".py":
        imports = re.findall(r"^(?:from\s+([\w\.]+)|import\s+([\w\.]+))", content, re.MULTILINE)
        flat_imports = [imp[0] or imp[1] for imp in imports if imp[0] or imp[1]]
        imports = flat_imports[:10]
        if "fastapi" in content:
            framework = "fastapi"
        elif "django" in content:
            framework = "django"
        elif "flask" in content:
            framework = "flask"
    elif any(x in ext_lower for x in ("js", "ts", "jsx", "tsx")):
        imports = re.findall(r"import\s+.*?from\s+['\"](.*?)['\"]", content)
        imports = imports[:10]
        if "react" in content:
            framework = "react"
        elif "express" in content:
            framework = "express"
        elif "next" in content:
            framework = "next"

    return {
        "module": module_name,
        "imports": imports,
        "framework": framework,
        "file_path": file_path,
        "extension": extension
    }


def chunk_code_file(
    content: str, 
    extension: str, 
    project_id: str, 
    file_path: str
) -> List[Dict[str, Any]]:
    """
    Chunks a code file using Tree-sitter syntax parsing.
    If parsing fails or no symbols are detected, falls back to 500-token overlapping chunks.
    """
    ts_lang_name = get_treesitter_language(extension)
    lines = content.splitlines()
    file_meta = extract_file_metadata(content, file_path, extension)
    
    # 0. High file size safeguard (>500KB files bypass tree-sitter AST to prevent CPU bottlenecks)
    if len(content) > 500000 or not ts_lang_name:
        if len(content) > 500000:
            logger.warning(f"File '{file_path}' exceeds 500KB ({len(content)} bytes). Bypassing Tree-sitter AST parser for performance.")
        fallback_chunks = fallback_chunker(content, token_limit=500, overlap=50)
        return [
            {
                "project_id": project_id,
                "file_path": file_path,
                "language": extension.replace(".", ""),
                "symbol_name": None,
                "symbol_type": None,
                "parent_class": None,
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "content": c["content"],
                "chunking_method": "fallback",
                "metadata": file_meta
            }
            for c in fallback_chunks
        ]

    try:
        parser = get_cached_ts_parser(ts_lang_name)
        source_bytes = bytes(content, "utf-8")
        tree = parser.parse(source_bytes)
        
        # Extract AST symbols
        raw_symbols = traverse_ast(tree.root_node, source_bytes)
        
        if not raw_symbols:
            logger.info(f"No symbols found in {file_path}. Falling back to standard chunker.")
            raise ValueError("No symbols found")
            
        chunks = []
        for sym in raw_symbols:
            # Find and prepend preceding comments
            start_line_idx = sym["start_line"] - 1
            comments = get_preceding_comments(lines, start_line_idx, ts_lang_name)
            full_content = comments + sym["content"]
            
            chunk_meta = dict(file_meta)
            chunk_meta.update({
                "class": sym.get("parent_class"),
                "function": sym.get("symbol_name"),
                "symbol_type": sym.get("symbol_type")
            })

            chunks.append({
                "project_id": project_id,
                "file_path": file_path,
                "language": extension.replace(".", ""),
                "symbol_name": sym["symbol_name"],
                "symbol_type": sym["symbol_type"],
                "parent_class": sym["parent_class"],
                "start_line": sym["start_line"],
                "end_line": sym["end_line"],
                "content": full_content,
                "chunking_method": "ast",
                "metadata": chunk_meta
            })
            
        return chunks
        
    except Exception as e:
        logger.info(f"Tree-sitter parsing for {file_path} failed ({e}). Using fallback chunker.")
        fallback_chunks = fallback_chunker(content, token_limit=500, overlap=50)
        return [
            {
                "project_id": project_id,
                "file_path": file_path,
                "language": extension.replace(".", ""),
                "symbol_name": None,
                "symbol_type": None,
                "parent_class": None,
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "content": c["content"],
                "chunking_method": "fallback",
                "metadata": file_meta
            }
            for c in fallback_chunks
        ]


def chunk_file(
    content: str, 
    extension: str, 
    project_id: str, 
    file_path: str
) -> List[Dict[str, Any]]:
    """
    Main entry point for chunking. Chooses chunking strategy based on file type.
    """
    file_meta = extract_file_metadata(content, file_path, extension)

    # 1. Config files (.json, .yaml, .yml) NEVER use Tree-sitter
    if extension.lower() in (".json", ".yaml", ".yml", ".txt"):
        fallback_chunks = fallback_chunker(content, token_limit=500, overlap=50)
        return [
            {
                "project_id": project_id,
                "file_path": file_path,
                "language": extension.replace(".", ""),
                "symbol_name": None,
                "symbol_type": None,
                "parent_class": None,
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "content": c["content"],
                "chunking_method": "fallback",
                "metadata": file_meta
            }
            for c in fallback_chunks
        ]
        
    # 2. Markdown files split by headings
    elif extension.lower() == ".md":
        md_chunks = chunk_markdown(content)
        return [
            {
                "project_id": project_id,
                "file_path": file_path,
                "language": "md",
                "symbol_name": None,
                "symbol_type": "heading",
                "parent_class": None,
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "content": c["content"],
                "chunking_method": "markdown",
                "metadata": file_meta
            }
            for c in md_chunks
        ]
        
    # 3. Code files use Tree-sitter
    else:
        return chunk_code_file(content, extension, project_id, file_path)

