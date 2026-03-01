"""Repository cloning and structure analysis."""

from __future__ import annotations

import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any

import git

logger = logging.getLogger(__name__)

# Directories to skip during tree traversal
SKIP_DIRS = frozenset(
    {
        "node_modules",
        ".git",
        "__pycache__",
        "vendor",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "target",
        "venv",
        ".venv",
        "env",
        ".env",
        "coverage",
        ".coverage",
        ".pytest_cache",
        ".mypy_cache",
        "eggs",
        ".eggs",
        "*.egg-info",
        ".tox",
        ".cache",
        "htmlcov",
    }
)

# Entry point file patterns
ENTRY_POINT_PATTERNS = (
    "main.py",
    "app.py",
    "index.py",
    "server.py",
    "run.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "index.js",
    "index.ts",
    "index.jsx",
    "index.tsx",
    "app.js",
    "app.ts",
    "server.js",
    "server.ts",
    "main.go",
    "cmd/main.go",
    "main.rs",
    "lib.rs",
    "main.java",
    "Main.java",
    "Application.java",
    "main.swift",
    "main.rb",
    "app.rb",
    "config.ru",
    "main.c",
    "main.cpp",
    "Program.cs",
)

_GITHUB_URL_PATTERN = re.compile(
    r"^https?://(?:www\.)?github\.com/[\w\-\.]+/[\w\-\.]+(?:\.git)?/?$"
)


def clone_repository(url: str, target_dir: Path, depth: int = 1) -> Path:
    """Clone a GitHub repository to a local directory.

    Args:
        url: The GitHub repository URL.
        target_dir: Directory where the repository will be cloned.
        depth: Shallow clone depth (1 = only latest commit).

    Returns:
        Path to the cloned repository.

    Raises:
        ValueError: If the URL format is invalid.
        RuntimeError: If the clone fails.
    """
    if not _GITHUB_URL_PATTERN.match(url):
        raise ValueError(
            f"Invalid GitHub URL: {url!r}. "
            "Expected format: https://github.com/owner/repo"
        )

    # Derive repo name from URL
    repo_name = url.rstrip("/").rstrip(".git").rsplit("/", 1)[-1]
    clone_path = target_dir / repo_name

    # Clean up any previous failed clone
    if clone_path.exists():
        shutil.rmtree(clone_path)

    target_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Cloning %s → %s (depth=%d)", url, clone_path, depth)

    try:
        git.Repo.clone_from(
            url,
            clone_path,
            depth=depth,
            multi_options=["--single-branch"],
        )
    except git.exc.GitCommandError as exc:
        # Clean up on failure
        if clone_path.exists():
            shutil.rmtree(clone_path, ignore_errors=True)
        error_msg = str(exc)
        if "Repository not found" in error_msg or "not found" in error_msg.lower():
            raise RuntimeError(
                f"Repository not found or is private: {url}"
            ) from exc
        if "Could not resolve host" in error_msg or "network" in error_msg.lower():
            raise RuntimeError(
                f"Network error while cloning {url}. Check internet connection."
            ) from exc
        raise RuntimeError(f"Failed to clone {url}: {exc}") from exc

    logger.info("Clone complete: %s", clone_path)
    return clone_path


def analyze_structure(repo_path: Path) -> dict[str, Any]:
    """Analyze the directory structure of a repository.

    Args:
        repo_path: Path to the cloned repository.

    Returns:
        Dictionary with file_tree, entry_points, total_files, total_size.
    """
    logger.debug("Analyzing structure of %s", repo_path)

    file_tree_lines: list[str] = []
    entry_points: list[str] = []
    total_files = 0
    total_size = 0

    def _walk(directory: Path, prefix: str = "") -> None:
        nonlocal total_files, total_size

        try:
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return

        dirs = [e for e in entries if e.is_dir() and e.name not in SKIP_DIRS]
        files = [e for e in entries if e.is_file()]

        for i, d in enumerate(dirs):
            connector = "└── " if (i == len(dirs) - 1 and not files) else "├── "
            file_tree_lines.append(f"{prefix}{connector}{d.name}/")
            extension = "    " if (i == len(dirs) - 1 and not files) else "│   "
            _walk(d, prefix + extension)

        for i, f in enumerate(files):
            connector = "└── " if i == len(files) - 1 else "├── "
            file_tree_lines.append(f"{prefix}{connector}{f.name}")
            total_files += 1
            try:
                size = f.stat().st_size
                total_size += size
            except OSError:
                pass

            # Check if it's an entry point
            rel = str(f.relative_to(repo_path))
            if f.name in ENTRY_POINT_PATTERNS or rel in ENTRY_POINT_PATTERNS:
                entry_points.append(rel)

    # Start tree with repo name
    file_tree_lines.append(f"{repo_path.name}/")
    _walk(repo_path)

    file_tree = "\n".join(file_tree_lines)
    logger.debug(
        "Structure: %d files, %d bytes, %d entry points",
        total_files,
        total_size,
        len(entry_points),
    )

    return {
        "file_tree": file_tree,
        "entry_points": entry_points,
        "total_files": total_files,
        "total_size": total_size,
    }
