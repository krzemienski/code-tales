"""Configuration for code-tales."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CodeTalesConfig(BaseModel):
    """Configuration for the code-tales pipeline."""

    anthropic_api_key: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    output_dir: Path = Field(default_factory=lambda: Path("./output"))
    temp_dir: Path = Field(default_factory=lambda: Path("/tmp/code-tales"))
    clone_depth: int = 1
    max_files_to_analyze: int = 100
    max_file_size_bytes: int = 100_000
    claude_model: str = "claude-sonnet-4-6"
    max_script_tokens: int = 4096

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def from_env(cls) -> "CodeTalesConfig":
        """Load configuration from environment variables."""
        return cls(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            elevenlabs_api_key=os.environ.get("ELEVENLABS_API_KEY"),
            output_dir=Path(os.environ.get("CODE_TALES_OUTPUT_DIR", "./output")),
            temp_dir=Path(os.environ.get("CODE_TALES_TEMP_DIR", "/tmp/code-tales")),
            clone_depth=int(os.environ.get("CODE_TALES_CLONE_DEPTH", "1")),
            max_files_to_analyze=int(
                os.environ.get("CODE_TALES_MAX_FILES", "100")
            ),
            max_file_size_bytes=int(
                os.environ.get("CODE_TALES_MAX_FILE_SIZE", "100000")
            ),
            claude_model=os.environ.get("CODE_TALES_CLAUDE_MODEL", "claude-sonnet-4-6"),
            max_script_tokens=int(
                os.environ.get("CODE_TALES_MAX_TOKENS", "4096")
            ),
        )

    def ensure_dirs(self) -> None:
        """Create necessary directories."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured directories: output=%s, temp=%s", self.output_dir, self.temp_dir)
