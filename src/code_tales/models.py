"""Pydantic models for code-tales."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Language(BaseModel):
    """A programming language detected in the repository."""

    name: str
    percentage: float
    file_count: int


class Dependency(BaseModel):
    """A dependency found in the repository."""

    name: str
    version: Optional[str] = None
    source: str  # e.g. "package.json", "requirements.txt"


class FileInfo(BaseModel):
    """Information about a file in the repository."""

    path: str
    language: str
    size_bytes: int
    is_entry_point: bool = False


class RepoAnalysis(BaseModel):
    """Complete analysis of a repository."""

    name: str
    description: str = ""
    url: str = ""
    languages: list[Language] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    file_tree: str = ""
    key_files: list[FileInfo] = Field(default_factory=list)
    total_files: int = 0
    total_lines: int = 0
    frameworks: list[str] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)
    readme_content: Optional[str] = None


class ScriptSection(BaseModel):
    """A section of a narration script."""

    heading: str
    content: str
    voice_direction: Optional[str] = None  # e.g. "speak slowly here"


class NarrationScript(BaseModel):
    """A complete narration script for a repository."""

    title: str
    style: str
    sections: list[ScriptSection] = Field(default_factory=list)
    word_count: int = 0
    estimated_duration_seconds: int = 0


class AudioOutput(BaseModel):
    """The output of the code-tales pipeline."""

    script: NarrationScript
    audio_path: Optional[Path] = None
    text_path: Path
    style: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"arbitrary_types_allowed": True}


class StyleConfig(BaseModel):
    """Configuration for a narrative style."""

    name: str
    description: str
    tone: str
    structure_template: str
    voice_id: str
    voice_params: dict[str, Any] = Field(default_factory=dict)
    example_opener: str = ""
