"""code-tales: Transform GitHub repositories into narrated audio stories."""

from .config import CodeTalesConfig
from .models import AudioOutput, NarrationScript, RepoAnalysis
from .pipeline.orchestrate import CodeTalesPipeline
from .styles.registry import StyleRegistry, get_registry

__version__ = "0.1.0"
__author__ = "krzemienski"

__all__ = [
    "__version__",
    "CodeTalesPipeline",
    "StyleRegistry",
    "get_registry",
    "RepoAnalysis",
    "NarrationScript",
    "AudioOutput",
    "CodeTalesConfig",
]
