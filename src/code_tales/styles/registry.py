"""Style registry for loading and accessing narrative styles."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml

from ..models import StyleConfig

logger = logging.getLogger(__name__)

_STYLES_DIR = Path(__file__).parent
_registry_instance: Optional["StyleRegistry"] = None


class StyleRegistry:
    """Registry for narrative style configurations.

    Loads built-in styles from YAML files in the styles/ directory
    and supports loading custom styles from arbitrary paths.
    """

    def __init__(self) -> None:
        self._styles: dict[str, StyleConfig] = {}

    def load_builtin_styles(self) -> dict[str, StyleConfig]:
        """Load all built-in YAML style files from the styles/ directory.

        Returns:
            Dictionary mapping style name → StyleConfig.
        """
        yaml_files = sorted(_STYLES_DIR.glob("*.yaml"))
        for yaml_file in yaml_files:
            try:
                style = self._load_yaml(yaml_file)
                self._styles[style.name] = style
                logger.debug("Loaded built-in style: %s", style.name)
            except Exception as exc:
                logger.warning("Failed to load style %s: %s", yaml_file.name, exc)

        logger.info("Loaded %d built-in styles", len(self._styles))
        return self._styles

    def load_custom_style(self, path: Path) -> StyleConfig:
        """Load a single custom style YAML file.

        Args:
            path: Path to the YAML file.

        Returns:
            The loaded StyleConfig.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the YAML is invalid or missing required fields.
        """
        if not path.exists():
            raise FileNotFoundError(f"Custom style file not found: {path}")
        style = self._load_yaml(path)
        self._styles[style.name] = style
        logger.info("Loaded custom style: %s", style.name)
        return style

    def get_style(self, name: str) -> StyleConfig:
        """Get a style by name.

        Args:
            name: The style name (e.g., 'documentary', 'fiction').

        Returns:
            The StyleConfig for the requested style.

        Raises:
            KeyError: If the style is not found.
        """
        if not self._styles:
            self.load_builtin_styles()

        if name not in self._styles:
            available = ", ".join(sorted(self._styles.keys()))
            raise KeyError(
                f"Style '{name}' not found. Available styles: {available}"
            )
        return self._styles[name]

    def list_styles(self) -> list[StyleConfig]:
        """Return all available styles.

        Returns:
            List of StyleConfig objects sorted by name.
        """
        if not self._styles:
            self.load_builtin_styles()
        return sorted(self._styles.values(), key=lambda s: s.name)

    def _load_yaml(self, path: Path) -> StyleConfig:
        """Load and validate a YAML style file.

        Args:
            path: Path to the YAML file.

        Returns:
            Validated StyleConfig.

        Raises:
            ValueError: If the YAML is malformed or missing required fields.
        """
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML in {path.name}: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValueError(f"Style file {path.name} must contain a YAML mapping")

        required = {"name", "description", "tone", "structure_template", "voice_id"}
        missing = required - raw.keys()
        if missing:
            raise ValueError(
                f"Style file {path.name} missing required fields: {missing}"
            )

        # Ensure voice_params is a dict
        if "voice_params" not in raw:
            raw["voice_params"] = {}

        return StyleConfig(**raw)


def get_registry() -> StyleRegistry:
    """Get the singleton StyleRegistry instance.

    Returns:
        The global StyleRegistry, initializing it if needed.
    """
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = StyleRegistry()
        _registry_instance.load_builtin_styles()
    return _registry_instance
