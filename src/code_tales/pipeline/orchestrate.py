"""Full pipeline orchestrator for code-tales."""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ..config import CodeTalesConfig
from ..models import AudioOutput, NarrationScript
from ..styles.registry import StyleRegistry, get_registry
from .analyze import analyze_repository
from .clone import clone_repository
from .narrate import generate_script
from .synthesize import save_text_output, synthesize_audio

logger = logging.getLogger(__name__)
console = Console()


class CodeTalesPipeline:
    """Orchestrates the full code-tales pipeline.

    Stages:
      1. Resolve repository (clone URL or validate local path)
      2. Analyze repository structure and metadata
      3. Generate narration script via Claude
      4. Synthesize audio via ElevenLabs (or save text only)
    """

    def __init__(self, config: Optional[CodeTalesConfig] = None) -> None:
        """Initialize the pipeline.

        Args:
            config: Pipeline configuration. Defaults to CodeTalesConfig.from_env().
        """
        self.config = config or CodeTalesConfig.from_env()
        self.config.ensure_dirs()
        self._registry = get_registry()

    def generate(
        self,
        repo_url_or_path: str,
        style_name: str,
        output_dir: Optional[Path] = None,
    ) -> AudioOutput:
        """Run the complete pipeline: clone → analyze → narrate → synthesize.

        Args:
            repo_url_or_path: GitHub URL or local path to a git repository.
            style_name: Name of the narrative style to use.
            output_dir: Directory for output files. Defaults to config.output_dir.

        Returns:
            AudioOutput with paths to generated files and the script.
        """
        out_dir = output_dir or self.config.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        style = self._registry.get_style(style_name)
        temp_dir: Optional[Path] = None

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        ) as progress:

            # Stage 1: Resolve repository
            task = progress.add_task("Resolving repository...", total=None)
            try:
                repo_path, temp_dir = self._resolve_repo(repo_url_or_path)
            finally:
                progress.update(task, description="Repository resolved")

            # Stage 2: Analyze
            progress.update(task, description="Analyzing repository structure...")
            analysis = analyze_repository(repo_path, self.config)
            progress.update(
                task,
                description=f"Analysis complete: {analysis.total_files} files, "
                f"{len(analysis.languages)} languages",
            )

            # Stage 3: Narrate
            progress.update(task, description=f"Generating script [{style_name}]...")
            script = generate_script(analysis, style, self.config)
            progress.update(
                task,
                description=f"Script ready: {script.word_count} words "
                f"(~{script.estimated_duration_seconds // 60}m)",
            )

            # Stage 4: Synthesize
            audio_file = out_dir / f"{analysis.name}-{style_name}.mp3"
            if self.config.elevenlabs_api_key:
                progress.update(task, description="Synthesizing audio...")
            else:
                progress.update(task, description="Saving text output (no TTS key)...")

            result_path = synthesize_audio(script, style, audio_file, self.config)

            # Determine if we got audio or text
            if result_path.suffix == ".mp3":
                audio_path: Optional[Path] = result_path
                text_path = result_path.with_suffix(".md")
            else:
                audio_path = None
                text_path = result_path

            progress.update(task, description="[green]Done!")

        # Cleanup temp dir
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.debug("Cleaned up temp dir: %s", temp_dir)

        output = AudioOutput(
            script=script,
            audio_path=audio_path,
            text_path=text_path,
            style=style_name,
        )

        console.print(f"\n[bold green]Story generated![/bold green]")
        console.print(f"  Script: [cyan]{text_path}[/cyan]")
        if audio_path:
            console.print(f"  Audio:  [cyan]{audio_path}[/cyan]")
        console.print(
            f"  Style: {style_name} | "
            f"Words: {script.word_count:,} | "
            f"Duration: {script.estimated_duration_seconds // 60}m {script.estimated_duration_seconds % 60}s"
        )

        return output

    def preview(
        self,
        repo_url_or_path: str,
        style_name: str,
    ) -> NarrationScript:
        """Run clone → analyze → narrate without TTS synthesis.

        Args:
            repo_url_or_path: GitHub URL or local path to a git repository.
            style_name: Name of the narrative style to use.

        Returns:
            The generated NarrationScript for inspection.
        """
        style = self._registry.get_style(style_name)
        temp_dir: Optional[Path] = None

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        ) as progress:

            task = progress.add_task("Resolving repository...", total=None)
            try:
                repo_path, temp_dir = self._resolve_repo(repo_url_or_path)
            finally:
                progress.update(task, description="Repository resolved")

            progress.update(task, description="Analyzing repository...")
            analysis = analyze_repository(repo_path, self.config)

            progress.update(task, description=f"Generating {style_name} script...")
            script = generate_script(analysis, style, self.config)
            progress.update(task, description="[green]Preview ready!")

        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

        return script

    def _resolve_repo(self, repo_url_or_path: str) -> tuple[Path, Optional[Path]]:
        """Resolve a URL or local path to a repository path.

        Args:
            repo_url_or_path: GitHub URL or local filesystem path.

        Returns:
            Tuple of (repo_path, temp_dir_to_cleanup).
            temp_dir is non-None only when we cloned a URL.

        Raises:
            ValueError: If the local path doesn't exist or isn't a git repo.
            RuntimeError: If cloning fails.
        """
        if repo_url_or_path.startswith(("http://", "https://", "git@")):
            temp_dir = Path(tempfile.mkdtemp(prefix="code-tales-"))
            logger.debug("Cloning %s to %s", repo_url_or_path, temp_dir)
            repo_path = clone_repository(
                url=repo_url_or_path,
                target_dir=temp_dir,
                depth=self.config.clone_depth,
            )
            return repo_path, temp_dir

        # Local path
        local = Path(repo_url_or_path).expanduser().resolve()
        if not local.exists():
            raise ValueError(f"Local path does not exist: {local}")
        if not local.is_dir():
            raise ValueError(f"Local path is not a directory: {local}")
        if not (local / ".git").exists():
            raise ValueError(
                f"Local path is not a git repository (no .git dir): {local}"
            )
        logger.debug("Using local repo: %s", local)
        return local, None
