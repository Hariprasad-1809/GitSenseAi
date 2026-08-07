# GitSense AI - Uvicorn / WatchFiles Reload Fix Report

## Overview
This report details the root cause analysis, implementation details, and verification results for resolving the server auto-reload issue during repository cloning and background indexing in GitSense AI.

---

## 1. Problem Description & Symptoms
When a GitHub repository or ZIP archive was ingested by the backend:
1. The repository was cloned shallowly into `backend/data/repos/<project_id>/`.
2. The cloned repository contained Python (`.py`) files.
3. Uvicorn's WatchFiles auto-reloader detected the newly created `.py` files and triggered an immediate server restart.
4. The background indexing task running in the FastAPI event loop was abruptly terminated.
5. The database status remained stuck at `"cloning"` or became orphaned.
6. The frontend status endpoint (`GET /api/ingest/status/{project_id}`) polled continuously without ever receiving a `"completed"` status.

---

## 2. Root Cause Analysis

### A. Uvicorn's `WatchFilesReload` Watch Root Selection
Uvicorn's `WatchFilesReload` supervisor (`uvicorn.supervisors.watchfilesreload.WatchFilesReload`) constructs its watch list as follows:
```python
self.reload_dirs = []
for directory in config.reload_dirs:
    if Path.cwd() not in directory.parents:
        self.reload_dirs.append(directory)
if Path.cwd() not in self.reload_dirs:
    self.reload_dirs.append(Path.cwd())
```
Even when `reload_dirs=["app"]` was specified, Uvicorn automatically appended `Path.cwd()` (the `backend/` root directory) to `reload_dirs`. Consequently, WatchFiles monitored the entire `backend/` workspace recursively, including `backend/data/repos/`.

### B. Path Comparison Failure in Uvicorn's `FileFilter`
Previously, `reload_excludes` was configured as relative paths and globs: `["data/*", "data/**", "data", "scratch/*", "scratch"]`.

1. **Glob Patterns** (`"data/*"`, `"data/**"`): `Path("data/*").is_dir()` returns `False`. Uvicorn placed them in `self.excludes` (pattern array).
2. **Relative Paths** (`"data"`, `"scratch"`): `Path("data").is_dir()` returned `True` (if the directory existed), placing `WindowsPath('data')` into `self.exclude_dirs`.
3. When WatchFiles detected newly created files (e.g. `D:\projects\GitSense_Ai\backend\data\repos\<project_id>\main.py`), WatchFiles yielded **resolved absolute paths** (`WindowsPath('D:/projects/GitSense_Ai/backend/data/repos/...')`).
4. Uvicorn's `FileFilter` checked directory exclusions using:
   ```python
   for exclude_dir in self.exclude_dirs:
       if exclude_dir in path.parents:
           return False
   ```
   Evaluating `WindowsPath('data') in WindowsPath('D:/projects/GitSense_Ai/backend/data/repos/...').parents` returned **`False`** because a relative `WindowsPath` is never present in the `.parents` tuple of an absolute `WindowsPath`.
5. `FileFilter` also checked glob patterns via `path.match("data/*")` against absolute paths, which returned **`False`**.
6. As a result, `FileFilter` returned `True` for every cloned `.py` file, triggering a Uvicorn process restart and terminating the background task.

---

## 3. Solution & Implementation Details

To ensure WatchFiles ignores cloned repository storage without restarting the server:

1. **Directory Pre-Creation**:
   All storage directories (`data`, `data/repos`, `data/uploads`, `scratch`) are explicitly created at server startup before Uvicorn initializes `FileFilter`. This guarantees `Path(...).is_dir()` evaluates to `True`.

2. **Resolved Absolute Path Exclusion**:
   `reload_dirs` and `reload_excludes` in `run.py` and `app/main.py` are converted to resolved absolute path strings:
   - `str(Path("app").resolve())`
   - `str(Path("data").resolve())`
   - `str(settings.repo_path)` (`Path("data/repos").resolve()`)
   - `str(settings.upload_path)` (`Path("data/uploads").resolve()`)
   - `str(Path("scratch").resolve())`

   Because `exclude_dirs` now contains absolute `WindowsPath` instances (such as `WindowsPath('D:/projects/GitSense_Ai/backend/data')`), the check `exclude_dir in path.parents` evaluates to **`True`** for any file inside `data/repos/`. `FileFilter` returns `False`, suppressing server reloads.

3. **Startup Logging**:
   Startup logging was added to `run.py`, `app/main.py`'s `if __name__ == "__main__":` runner, and FastAPI's `lifespan` handler. On application startup, the server logs:
   - **Watched directories**: `['D:\\projects\\GitSense_Ai\\backend\\app']`
   - **Excluded directories**: `['D:\\projects\\GitSense_Ai\\backend\\data', 'D:\\projects\\GitSense_Ai\\backend\\data\\repos', 'D:\\projects\\GitSense_Ai\\backend\\data\\uploads', 'D:\\projects\\GitSense_Ai\\backend\\scratch']`
   - **Repository clone directory**: `'D:\\projects\\GitSense_Ai\\backend\\data\\repos'`

---

## 4. Files Changed

### 1. `backend/run.py` ([run.py](file:///d:/projects/GitSense_Ai/backend/run.py))
- Added storage directory pre-creation for `data`, `data/repos`, `data/uploads`, and `scratch`.
- Configured Uvicorn `reload_dirs` and `reload_excludes` using resolved absolute path strings.
- Added startup logging for watched directories, excluded directories, and repository clone directory.

### 2. `backend/app/main.py` ([main.py](file:///d:/projects/GitSense_Ai/backend/app/main.py))
- Added startup logging in `lifespan` handler displaying watched directories, excluded directories, and repository clone directory.
- Updated `if __name__ == "__main__":` runner block to mirror `run.py`'s resolved absolute path exclusion configuration.

---

## 5. Verification & Results

1. **WatchFiles Exclusion Verification**:
   Verified using `uvicorn.supervisors.watchfilesreload.FileFilter`:
   - Cloned repository Python file (`data/repos/sample_repo/subfolder/module.py`): `WatchFiles` filter returned **`False`** (Excluded, server will NOT reload).
   - Application Python file (`app/main.py`): `WatchFiles` filter returned **`True`** (Included, server reloads on code change).

2. **Pipeline Progress & Ingestion Verification**:
   Ran background ingestion pipeline on a test repository containing 54 Python files:
   - **Cloning & Extraction**: Completed without server interruption.
   - **AST Parsing Progress**: Incremented from `0/54` → `1/54` → ... → `54/54`.
   - **Embedding Generation**: Processed all code chunks using local embeddings model.
   - **Database Persistence**: Vector store and project metadata saved successfully.
   - **Final Status**: Transitioned to `"completed"` with status dictionary:
     ```python
     {
         'project_name': 'test_progress_repo',
         'status': 'completed',
         'files_processed': 54,
         'total_files': 54,
         'percentage': 100.0,
         'error': None
     }
     ```
