"""Repository metadata extraction and analysis."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from ..config import CodeTalesConfig
from ..models import Dependency, FileInfo, Language, RepoAnalysis
from .clone import SKIP_DIRS, analyze_structure

logger = logging.getLogger(__name__)

# Map file extensions → language names
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".swift": "Swift",
    ".rb": "Ruby",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".c": "C",
    ".h": "C/C++",
    ".cs": "C#",
    ".php": "PHP",
    ".scala": "Scala",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".hs": "Haskell",
    ".ml": "OCaml",
    ".r": "R",
    ".R": "R",
    ".lua": "Lua",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Shell",
    ".dart": "Dart",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SASS",
    ".less": "LESS",
    ".tf": "Terraform",
    ".sql": "SQL",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".md": "Markdown",
}

# Key configuration / definition files worth reading
KEY_CONFIG_FILES = frozenset(
    {
        "README.md",
        "README.rst",
        "README.txt",
        "README",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "Gemfile",
        "pom.xml",
        "build.gradle",
        "Package.swift",
        "Makefile",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        ".env.example",
        "config.yaml",
        "config.yml",
        "config.json",
    }
)


def analyze_repository(repo_path: Path, config: CodeTalesConfig) -> RepoAnalysis:
    """Orchestrate full repository analysis.

    Args:
        repo_path: Path to the cloned repository.
        config: Pipeline configuration.

    Returns:
        Complete RepoAnalysis with all extracted metadata.
    """
    logger.info("Analyzing repository: %s", repo_path)

    structure = analyze_structure(repo_path)
    languages = _detect_languages(repo_path)
    dependencies = _extract_dependencies(repo_path)
    frameworks = _detect_frameworks(repo_path, languages)
    patterns = _detect_patterns(repo_path)
    key_files = _select_key_files(repo_path, config, structure["entry_points"])
    readme_content = _read_readme(repo_path)

    # Count total lines across key files
    total_lines = 0
    for kf in key_files:
        try:
            file_path = repo_path / kf.path
            lines = file_path.read_text(encoding="utf-8", errors="replace").count("\n")
            total_lines += lines
        except OSError:
            pass

    return RepoAnalysis(
        name=repo_path.name,
        description=_extract_description(readme_content),
        languages=languages,
        dependencies=dependencies,
        file_tree=structure["file_tree"],
        key_files=key_files,
        total_files=structure["total_files"],
        total_lines=total_lines,
        frameworks=frameworks,
        patterns=patterns,
        readme_content=readme_content,
    )


def _detect_languages(repo_path: Path) -> list[Language]:
    """Detect programming languages by file extension counts."""
    lang_counts: dict[str, int] = {}
    total = 0

    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue
        # Skip excluded directories
        parts = set(file_path.relative_to(repo_path).parts[:-1])
        if parts & SKIP_DIRS:
            continue

        ext = file_path.suffix.lower()
        lang = EXTENSION_TO_LANGUAGE.get(ext)
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
            total += 1

    if not total:
        return []

    languages = [
        Language(
            name=lang,
            percentage=round(count / total * 100, 1),
            file_count=count,
        )
        for lang, count in sorted(lang_counts.items(), key=lambda x: -x[1])
    ]
    return languages


def _extract_dependencies(repo_path: Path) -> list[Dependency]:
    """Extract dependencies from common package managers."""
    deps: list[Dependency] = []

    # package.json (npm/yarn)
    pkg_json = repo_path / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            for section in ("dependencies", "devDependencies", "peerDependencies"):
                for name, version in (data.get(section) or {}).items():
                    deps.append(
                        Dependency(name=name, version=str(version), source="package.json")
                    )
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("Could not parse package.json: %s", exc)

    # requirements.txt
    req_txt = repo_path / "requirements.txt"
    if req_txt.exists():
        try:
            for line in req_txt.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                match = re.match(r"^([A-Za-z0-9_\-\.]+)\s*([><=!~^].*)?$", line)
                if match:
                    deps.append(
                        Dependency(
                            name=match.group(1),
                            version=match.group(2) or None,
                            source="requirements.txt",
                        )
                    )
        except OSError as exc:
            logger.debug("Could not parse requirements.txt: %s", exc)

    # pyproject.toml
    pyproject = repo_path / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            # Simple regex extraction for dependencies array
            deps_block = re.search(
                r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL
            )
            if deps_block:
                for item in re.findall(r'"([^"]+)"', deps_block.group(1)):
                    match = re.match(r"^([A-Za-z0-9_\-\.]+)\s*([><=!~^].*)?$", item)
                    if match:
                        deps.append(
                            Dependency(
                                name=match.group(1),
                                version=match.group(2) or None,
                                source="pyproject.toml",
                            )
                        )
        except OSError as exc:
            logger.debug("Could not parse pyproject.toml: %s", exc)

    # Cargo.toml (Rust)
    cargo = repo_path / "Cargo.toml"
    if cargo.exists():
        try:
            content = cargo.read_text(encoding="utf-8")
            in_deps = False
            for line in content.splitlines():
                if re.match(r"^\[dependencies\]", line):
                    in_deps = True
                    continue
                if re.match(r"^\[", line):
                    in_deps = False
                if in_deps:
                    match = re.match(r'^(\w[\w\-]*)\s*=\s*"([^"]+)"', line)
                    if match:
                        deps.append(
                            Dependency(
                                name=match.group(1),
                                version=match.group(2),
                                source="Cargo.toml",
                            )
                        )
        except OSError as exc:
            logger.debug("Could not parse Cargo.toml: %s", exc)

    # go.mod
    go_mod = repo_path / "go.mod"
    if go_mod.exists():
        try:
            content = go_mod.read_text(encoding="utf-8")
            in_require = False
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("require ("):
                    in_require = True
                    continue
                if in_require and stripped == ")":
                    in_require = False
                    continue
                if in_require or stripped.startswith("require "):
                    match = re.search(r'([\w\./\-]+)\s+(v[\d\.]+)', stripped)
                    if match:
                        deps.append(
                            Dependency(
                                name=match.group(1),
                                version=match.group(2),
                                source="go.mod",
                            )
                        )
        except OSError as exc:
            logger.debug("Could not parse go.mod: %s", exc)

    # Gemfile (Ruby)
    gemfile = repo_path / "Gemfile"
    if gemfile.exists():
        try:
            for line in gemfile.read_text(encoding="utf-8").splitlines():
                match = re.match(r"""^\s*gem\s+['"]([^'"]+)['"](?:,\s*['"]([^'"]+)['"])?""", line)
                if match:
                    deps.append(
                        Dependency(
                            name=match.group(1),
                            version=match.group(2) or None,
                            source="Gemfile",
                        )
                    )
        except OSError as exc:
            logger.debug("Could not parse Gemfile: %s", exc)

    # Package.swift
    pkg_swift = repo_path / "Package.swift"
    if pkg_swift.exists():
        try:
            content = pkg_swift.read_text(encoding="utf-8")
            for match in re.finditer(r'\.package\(url:\s*"([^"]+)"', content):
                name = match.group(1).rstrip("/").rsplit("/", 1)[-1].replace(".git", "")
                deps.append(Dependency(name=name, source="Package.swift"))
        except OSError as exc:
            logger.debug("Could not parse Package.swift: %s", exc)

    # pom.xml (Maven)
    pom = repo_path / "pom.xml"
    if pom.exists():
        try:
            content = pom.read_text(encoding="utf-8")
            for match in re.finditer(
                r"<artifactId>([^<]+)</artifactId>.*?<version>([^<]+)</version>",
                content,
                re.DOTALL,
            ):
                deps.append(
                    Dependency(
                        name=match.group(1).strip(),
                        version=match.group(2).strip(),
                        source="pom.xml",
                    )
                )
        except OSError as exc:
            logger.debug("Could not parse pom.xml: %s", exc)

    logger.debug("Extracted %d dependencies", len(deps))
    return deps


def _detect_frameworks(repo_path: Path, languages: list[Language]) -> list[str]:
    """Detect frameworks and libraries used in the project."""
    frameworks: list[str] = []
    lang_names = {lang.name for lang in languages}

    # Check for framework-specific files / imports
    if "JavaScript" in lang_names or "TypeScript" in lang_names:
        pkg_json = repo_path / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                all_deps = {
                    **data.get("dependencies", {}),
                    **data.get("devDependencies", {}),
                }
                framework_map = {
                    "react": "React",
                    "vue": "Vue.js",
                    "angular": "Angular",
                    "@angular/core": "Angular",
                    "express": "Express",
                    "fastify": "Fastify",
                    "next": "Next.js",
                    "nuxt": "Nuxt.js",
                    "svelte": "Svelte",
                    "nest": "NestJS",
                    "@nestjs/core": "NestJS",
                    "koa": "Koa",
                    "hapi": "Hapi.js",
                    "graphql": "GraphQL",
                    "prisma": "Prisma",
                }
                for dep_key, fw_name in framework_map.items():
                    if dep_key in all_deps and fw_name not in frameworks:
                        frameworks.append(fw_name)
            except (json.JSONDecodeError, OSError):
                pass

        # Check for JSX/TSX files → React
        jsx_files = list(repo_path.rglob("*.jsx")) + list(repo_path.rglob("*.tsx"))
        if jsx_files and "React" not in frameworks:
            frameworks.append("React")

        # Check for .vue files → Vue
        vue_files = list(repo_path.rglob("*.vue"))
        if vue_files and "Vue.js" not in frameworks:
            frameworks.append("Vue.js")

    if "Python" in lang_names:
        # Django
        if (repo_path / "manage.py").exists() or list(repo_path.rglob("settings.py")):
            frameworks.append("Django")
        # Flask
        for py_file in list(repo_path.rglob("*.py"))[:20]:
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
                if "from flask import" in content or "import flask" in content.lower():
                    if "Flask" not in frameworks:
                        frameworks.append("Flask")
                if "from fastapi import" in content or "import fastapi" in content.lower():
                    if "FastAPI" not in frameworks:
                        frameworks.append("FastAPI")
                if "import anthropic" in content or "from anthropic" in content:
                    if "Anthropic SDK" not in frameworks:
                        frameworks.append("Anthropic SDK")
            except OSError:
                pass

    if "Go" in lang_names:
        go_mod = repo_path / "go.mod"
        if go_mod.exists():
            try:
                content = go_mod.read_text(encoding="utf-8")
                if "gin-gonic" in content:
                    frameworks.append("Gin")
                if "echo" in content:
                    frameworks.append("Echo")
                if "fiber" in content:
                    frameworks.append("Fiber")
                if "grpc" in content:
                    frameworks.append("gRPC")
            except OSError:
                pass

    if "Ruby" in lang_names:
        gemfile = repo_path / "Gemfile"
        if gemfile.exists():
            try:
                content = gemfile.read_text(encoding="utf-8")
                if "rails" in content.lower():
                    frameworks.append("Ruby on Rails")
                if "sinatra" in content.lower():
                    frameworks.append("Sinatra")
            except OSError:
                pass

    if "Java" in lang_names or "Kotlin" in lang_names:
        pom = repo_path / "pom.xml"
        build_gradle = repo_path / "build.gradle"
        for build_file in [pom, build_gradle]:
            if build_file.exists():
                try:
                    content = build_file.read_text(encoding="utf-8")
                    if "spring-boot" in content.lower() or "springframework" in content.lower():
                        if "Spring Boot" not in frameworks:
                            frameworks.append("Spring Boot")
                    if "quarkus" in content.lower() and "Quarkus" not in frameworks:
                        frameworks.append("Quarkus")
                except OSError:
                    pass

    if "Swift" in lang_names:
        pkg_swift = repo_path / "Package.swift"
        if pkg_swift.exists():
            try:
                content = pkg_swift.read_text(encoding="utf-8")
                if "vapor" in content.lower():
                    frameworks.append("Vapor")
                if "SwiftUI" in content:
                    frameworks.append("SwiftUI")
            except OSError:
                pass

    logger.debug("Detected frameworks: %s", frameworks)
    return frameworks


def _detect_patterns(repo_path: Path) -> list[str]:
    """Identify architectural patterns and project types."""
    patterns: list[str] = []

    # Monorepo detection
    workspace_files = [
        repo_path / "pnpm-workspace.yaml",
        repo_path / "lerna.json",
        repo_path / "nx.json",
        repo_path / "rush.json",
    ]
    if any(f.exists() for f in workspace_files):
        patterns.append("Monorepo")
    elif (repo_path / "packages").is_dir() or (repo_path / "apps").is_dir():
        patterns.append("Monorepo")

    # Microservices
    if (
        (repo_path / "services").is_dir()
        or (repo_path / "microservices").is_dir()
        or (repo_path / "docker-compose.yml").exists()
    ):
        patterns.append("Microservices")

    # REST API
    api_dirs = ["api", "routes", "controllers", "handlers", "endpoints"]
    if any((repo_path / d).is_dir() for d in api_dirs):
        patterns.append("REST API")

    # GraphQL
    gql_files = list(repo_path.rglob("*.graphql")) + list(repo_path.rglob("*.gql"))
    if gql_files:
        patterns.append("GraphQL")

    # CLI tool
    cli_files = ["cli.py", "cli.js", "cli.ts", "cmd/", "commands/"]
    if any(
        (repo_path / f).exists() for f in cli_files
    ) or list(repo_path.rglob("cli*.py")):
        patterns.append("CLI Tool")

    # Library / SDK
    src_dirs = list(repo_path.rglob("src/"))
    lib_dirs = list(repo_path.rglob("lib/"))
    if (src_dirs or lib_dirs) and not (repo_path / "index.html").exists():
        patterns.append("Library/SDK")

    # Web App
    if (
        (repo_path / "public").is_dir()
        or (repo_path / "static").is_dir()
        or (repo_path / "index.html").exists()
    ):
        patterns.append("Web Application")

    # Mobile
    if (repo_path / "android").is_dir() or (repo_path / "ios").is_dir():
        patterns.append("Mobile App")

    # MVC
    mvc_dirs = {"models", "views", "controllers"}
    existing = {d for d in mvc_dirs if (repo_path / d).is_dir()}
    if len(existing) >= 2:
        patterns.append("MVC Architecture")

    # Testing presence
    test_dirs = ["tests", "test", "__tests__", "spec", "specs"]
    if any((repo_path / d).is_dir() for d in test_dirs):
        patterns.append("Test Coverage")

    # CI/CD
    if (repo_path / ".github" / "workflows").is_dir() or (repo_path / ".gitlab-ci.yml").exists():
        patterns.append("CI/CD Pipeline")

    # Docker
    if (repo_path / "Dockerfile").exists() or (repo_path / "docker-compose.yml").exists():
        patterns.append("Containerized")

    logger.debug("Detected patterns: %s", patterns)
    return patterns


def _select_key_files(
    repo_path: Path, config: CodeTalesConfig, entry_points: list[str]
) -> list[FileInfo]:
    """Select the most important files for analysis.

    Prioritizes README, entry points, and config files. Respects max_files_to_analyze.
    Skips binary files and files exceeding max_file_size_bytes.
    """
    key_files: list[FileInfo] = []
    seen_paths: set[str] = set()

    def _add_file(file_path: Path) -> bool:
        rel = str(file_path.relative_to(repo_path))
        if rel in seen_paths:
            return False
        if not file_path.is_file():
            return False
        try:
            size = file_path.stat().st_size
        except OSError:
            return False
        if size > config.max_file_size_bytes:
            return False
        # Skip binary files
        try:
            file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return False

        ext = file_path.suffix.lower()
        lang = EXTENSION_TO_LANGUAGE.get(ext, ext.lstrip(".") or "unknown")
        is_entry = rel in entry_points or file_path.name in entry_points

        key_files.append(
            FileInfo(
                path=rel,
                language=lang,
                size_bytes=size,
                is_entry_point=is_entry,
            )
        )
        seen_paths.add(rel)
        return True

    # 1. README first
    for readme_name in ("README.md", "README.rst", "README.txt", "README"):
        readme = repo_path / readme_name
        if readme.exists():
            _add_file(readme)
            break

    # 2. Entry points
    for ep in entry_points[: config.max_files_to_analyze // 4]:
        _add_file(repo_path / ep)

    # 3. Key config files
    for fname in KEY_CONFIG_FILES:
        if len(key_files) >= config.max_files_to_analyze:
            break
        candidate = repo_path / fname
        if candidate.exists():
            _add_file(candidate)

    # 4. Source files (sorted by size descending — bigger = more important)
    source_extensions = {
        ".py", ".js", ".ts", ".go", ".rs", ".java", ".swift", ".rb",
        ".cpp", ".c", ".cs", ".tsx", ".jsx", ".kt", ".scala",
    }
    all_source: list[Path] = []
    for ext in source_extensions:
        all_source.extend(repo_path.rglob(f"*{ext}"))

    # Filter out skip dirs
    def _is_valid(p: Path) -> bool:
        parts = set(p.relative_to(repo_path).parts[:-1])
        return not (parts & SKIP_DIRS)

    all_source = [p for p in all_source if _is_valid(p)]
    all_source.sort(key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)

    for fp in all_source:
        if len(key_files) >= config.max_files_to_analyze:
            break
        _add_file(fp)

    logger.debug("Selected %d key files", len(key_files))
    return key_files


def _read_readme(repo_path: Path) -> Optional[str]:
    """Read the README file if present."""
    for readme_name in ("README.md", "README.rst", "README.txt", "README"):
        readme = repo_path / readme_name
        if readme.exists():
            try:
                content = readme.read_text(encoding="utf-8", errors="replace")
                # Truncate very long READMEs
                if len(content) > 10_000:
                    content = content[:10_000] + "\n... [truncated]"
                return content
            except OSError as exc:
                logger.debug("Could not read README: %s", exc)
    return None


def _extract_description(readme_content: Optional[str]) -> str:
    """Extract a short description from README content."""
    if not readme_content:
        return ""
    lines = readme_content.strip().splitlines()
    # Skip the title line (# ...)
    desc_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped:
            desc_lines.append(stripped)
        if len(desc_lines) >= 3:
            break
    return " ".join(desc_lines)[:500]
