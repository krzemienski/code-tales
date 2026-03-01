"""Pipeline modules for code-tales."""

from .clone import analyze_structure, clone_repository
from .analyze import analyze_repository
from .narrate import generate_script
from .synthesize import save_text_output, synthesize_audio
from .orchestrate import CodeTalesPipeline

__all__ = [
    "clone_repository",
    "analyze_structure",
    "analyze_repository",
    "generate_script",
    "synthesize_audio",
    "save_text_output",
    "CodeTalesPipeline",
]
