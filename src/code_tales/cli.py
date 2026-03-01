"""Click CLI for code-tales."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text

from .config import CodeTalesConfig
from .pipeline.orchestrate import CodeTalesPipeline
from .styles.registry import get_registry

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose debug logging.")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to a configuration file (not yet implemented; use env vars).",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, config_path: Optional[Path]) -> None:
    """code-tales: Transform GitHub repositories into narrated audio stories.

    Uses Claude AI to generate scripts and ElevenLabs TTS for audio synthesis.

    Set ANTHROPIC_API_KEY and optionally ELEVENLABS_API_KEY as environment variables.
    """
    ctx.ensure_object(dict)
    _setup_logging(verbose)
    ctx.obj["config"] = CodeTalesConfig.from_env()
    ctx.obj["verbose"] = verbose


@cli.command()
@click.option(
    "--repo",
    "repo_url",
    default=None,
    help="GitHub repository URL (e.g. https://github.com/owner/repo).",
)
@click.option(
    "--path",
    "local_path",
    default=None,
    type=click.Path(exists=True, path_type=Path),
    help="Path to a local git repository.",
)
@click.option(
    "--style",
    "-s",
    required=True,
    help="Narrative style to use. Run `code-tales list-styles` to see options.",
)
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for generated files. Defaults to ./output/.",
)
@click.option(
    "--no-audio",
    is_flag=True,
    default=False,
    help="Skip TTS synthesis and only generate text script.",
)
@click.pass_context
def generate(
    ctx: click.Context,
    repo_url: Optional[str],
    local_path: Optional[Path],
    style: str,
    output_dir: Optional[Path],
    no_audio: bool,
) -> None:
    """Generate a full narrated audio story from a repository.

    Provide either --repo (GitHub URL) or --path (local git repo).

    Examples:

    \b
      code-tales generate --repo https://github.com/fastapi/fastapi --style documentary
      code-tales generate --path ./my-project --style podcast --output ./stories/
      code-tales generate --repo https://github.com/django/django --style executive --no-audio
    """
    config: CodeTalesConfig = ctx.obj["config"]

    if not repo_url and not local_path:
        raise click.UsageError("Provide either --repo <url> or --path <local-path>.")
    if repo_url and local_path:
        raise click.UsageError("Provide only one of --repo or --path, not both.")

    if no_audio:
        config = config.model_copy(update={"elevenlabs_api_key": None})

    target = str(repo_url) if repo_url else str(local_path)
    out_dir = output_dir or config.output_dir

    try:
        pipeline = CodeTalesPipeline(config=config)
        result = pipeline.generate(
            repo_url_or_path=target,
            style_name=style,
            output_dir=out_dir,
        )
        console.print("\n[bold green]Generation complete![/bold green]")
        if result.audio_path:
            console.print(f"  Audio: [cyan]{result.audio_path}[/cyan]")
        console.print(f"  Script: [cyan]{result.text_path}[/cyan]")
    except KeyError as exc:
        console.print(f"[red]Style error:[/red] {exc}")
        console.print("Run [bold]code-tales list-styles[/bold] to see available styles.")
        sys.exit(1)
    except (ValueError, RuntimeError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)


@cli.command("list-styles")
@click.pass_context
def list_styles(ctx: click.Context) -> None:
    """List all available narrative styles with descriptions.

    Example:

    \b
      code-tales list-styles
    """
    registry = get_registry()
    styles = registry.list_styles()

    table = Table(
        title="Available Narrative Styles",
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
    )
    table.add_column("Style", style="bold cyan", min_width=14)
    table.add_column("Description", style="white")
    table.add_column("Tone", style="dim", max_width=40)
    table.add_column("Voice ID", style="dim", max_width=24)

    for s in styles:
        table.add_row(
            s.name,
            s.description[:80] + ("..." if len(s.description) > 80 else ""),
            s.tone[:60] + ("..." if len(s.tone) > 60 else ""),
            s.voice_id,
        )

    console.print(table)
    console.print(f"\n[dim]{len(styles)} styles available.[/dim]")
    console.print(
        "\nUsage: [bold]code-tales generate --repo <url> --style <name>[/bold]"
    )


@cli.command()
@click.option(
    "--repo",
    "repo_url",
    default=None,
    help="GitHub repository URL.",
)
@click.option(
    "--path",
    "local_path",
    default=None,
    type=click.Path(exists=True, path_type=Path),
    help="Path to a local git repository.",
)
@click.option(
    "--style",
    "-s",
    required=True,
    help="Narrative style to use.",
)
@click.pass_context
def preview(
    ctx: click.Context,
    repo_url: Optional[str],
    local_path: Optional[Path],
    style: str,
) -> None:
    """Preview the generated narration script without synthesizing audio.

    Runs the full analyze + narrate pipeline and prints the script to stdout.

    Examples:

    \b
      code-tales preview --repo https://github.com/tiangolo/fastapi --style fiction
      code-tales preview --path ./my-project --style technical
    """
    config: CodeTalesConfig = ctx.obj["config"]

    if not repo_url and not local_path:
        raise click.UsageError("Provide either --repo <url> or --path <local-path>.")
    if repo_url and local_path:
        raise click.UsageError("Provide only one of --repo or --path, not both.")

    target = str(repo_url) if repo_url else str(local_path)

    try:
        pipeline = CodeTalesPipeline(config=config)
        script = pipeline.preview(repo_url_or_path=target, style_name=style)
    except KeyError as exc:
        console.print(f"[red]Style error:[/red] {exc}")
        sys.exit(1)
    except (ValueError, RuntimeError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)

    # Print the script to console
    console.print(f"\n[bold magenta]# {script.title}[/bold magenta]")
    console.print(f"[dim]Style: {script.style} | Words: {script.word_count:,} | "
                  f"~{script.estimated_duration_seconds // 60}m {script.estimated_duration_seconds % 60}s[/dim]\n")

    for section in script.sections:
        console.print(f"[bold cyan]## {section.heading}[/bold cyan]")
        if section.voice_direction:
            console.print(f"[italic dim][{section.voice_direction}][/italic dim]")
        console.print(section.content)
        console.print()


if __name__ == "__main__":
    cli()
