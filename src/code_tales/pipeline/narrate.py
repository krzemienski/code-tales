"""Claude-powered narration script generation."""

from __future__ import annotations

import logging
import re
from typing import Optional

import anthropic

from ..config import CodeTalesConfig
from ..models import NarrationScript, RepoAnalysis, ScriptSection, StyleConfig

logger = logging.getLogger(__name__)

_WORDS_PER_MINUTE = 150  # Average speaking pace


def generate_script(
    analysis: RepoAnalysis,
    style: StyleConfig,
    config: CodeTalesConfig,
) -> NarrationScript:
    """Generate a narration script using Claude AI.

    Args:
        analysis: The repository analysis results.
        style: The narrative style configuration.
        config: Pipeline configuration.

    Returns:
        A structured NarrationScript ready for TTS synthesis.

    Raises:
        RuntimeError: If the Claude API call fails.
    """
    logger.info("Generating script for '%s' in '%s' style", analysis.name, style.name)

    api_key = config.anthropic_api_key
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    prompt = _build_prompt(analysis, style)
    system_message = _build_system_message(style)

    try:
        with client.messages.stream(
            model=config.claude_model,
            max_tokens=config.max_script_tokens,
            system=system_message,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            raw_text = stream.get_final_message().content[0].text
    except anthropic.AuthenticationError as exc:
        raise RuntimeError(
            "Invalid Anthropic API key. Set ANTHROPIC_API_KEY environment variable."
        ) from exc
    except anthropic.RateLimitError as exc:
        raise RuntimeError("Anthropic API rate limit exceeded. Please retry later.") from exc
    except anthropic.APIConnectionError as exc:
        raise RuntimeError(
            "Could not connect to Anthropic API. Check your internet connection."
        ) from exc
    except anthropic.APIStatusError as exc:
        raise RuntimeError(f"Anthropic API error ({exc.status_code}): {exc.message}") from exc

    logger.debug("Raw script length: %d chars", len(raw_text))
    script = _parse_script(raw_text, style)
    logger.info(
        "Script generated: %d sections, ~%d words, ~%ds",
        len(script.sections),
        script.word_count,
        script.estimated_duration_seconds,
    )
    return script


def _build_system_message(style: StyleConfig) -> str:
    """Build the system message that sets the narrative voice."""
    return f"""You are a creative writer crafting an audio narration script for a software repository.

Your narrative style: {style.name}
Tone: {style.tone}

CRITICAL FORMATTING RULES:
1. Structure your response using markdown headings (## Section Name) for each section.
2. Add voice directions in [brackets] at the start of paragraphs when helpful (e.g., [speak slowly], [with enthusiasm], [thoughtfully]).
3. Write for audio — avoid bullet points, tables, and markdown formatting in the body text.
4. Use natural speech patterns, contractions, and flowing sentences.
5. Each section should be 1-3 paragraphs of spoken text.
6. Do NOT include any preamble like "Here is the script:" — begin directly with the first section heading.
7. Make the content engaging and specific to this actual repository, not generic.
8. Opening line should be compelling and draw the listener in immediately."""


def _build_prompt(analysis: RepoAnalysis, style: StyleConfig) -> str:
    """Build the detailed prompt for Claude with repository analysis data."""
    # Format languages
    lang_summary = ", ".join(
        f"{lang.name} ({lang.percentage}%)" for lang in analysis.languages[:5]
    )
    if not lang_summary:
        lang_summary = "Unknown"

    # Format top dependencies
    top_deps = analysis.dependencies[:15]
    deps_text = (
        ", ".join(
            f"{d.name}{' ' + d.version if d.version else ''}" for d in top_deps
        )
        if top_deps
        else "None detected"
    )

    # Format frameworks
    frameworks_text = ", ".join(analysis.frameworks) if analysis.frameworks else "None detected"

    # Format patterns
    patterns_text = ", ".join(analysis.patterns) if analysis.patterns else "None detected"

    # Key files summary
    key_files_text = "\n".join(
        f"  - {kf.path} ({kf.language}, {kf.size_bytes} bytes)"
        + (" [ENTRY POINT]" if kf.is_entry_point else "")
        for kf in analysis.key_files[:20]
    )

    # README excerpt
    readme_excerpt = ""
    if analysis.readme_content:
        readme_excerpt = f"\n\nREADME (first 2000 chars):\n{analysis.readme_content[:2000]}"

    # File tree (truncated)
    tree_preview = analysis.file_tree[:2000] if analysis.file_tree else "N/A"
    if len(analysis.file_tree) > 2000:
        tree_preview += "\n  ... [truncated]"

    prompt = f"""Create a narration script for the following GitHub repository in the "{style.name}" style.

=== REPOSITORY INFORMATION ===
Name: {analysis.name}
Description: {analysis.description or "No description provided"}
Total Files: {analysis.total_files}
Total Lines: {analysis.total_lines:,}

Programming Languages: {lang_summary}
Frameworks & Libraries: {frameworks_text}
Architectural Patterns: {patterns_text}

Top Dependencies ({len(analysis.dependencies)} total):
{deps_text}

Key Files:
{key_files_text or "  No key files detected"}

Directory Structure:
{tree_preview}
{readme_excerpt}

=== STYLE INSTRUCTIONS ===
Style: {style.name}
Description: {style.description}
Tone: {style.tone}

Use this structure template as your guide for section headings and content:
{style.structure_template}

Example opening line for this style:
"{style.example_opener}"

=== YOUR TASK ===
Write a complete narration script for this repository following the style template.
Replace {{repo_name}} placeholders with "{analysis.name}".
Make it specific, insightful, and engaging — not generic.
Each section should flow naturally when read aloud.
Total script should be 500-1500 words depending on the style."""

    return prompt


def _parse_script(raw_text: str, style: StyleConfig) -> NarrationScript:
    """Parse Claude's response into structured NarrationScript sections.

    Splits on markdown headings (## or #) and extracts voice directions
    from [bracketed] text.
    """
    sections: list[ScriptSection] = []

    # Split on markdown headings (## or # at line start)
    heading_pattern = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)
    matches = list(heading_pattern.finditer(raw_text))

    if not matches:
        # Fallback: treat whole text as one section
        logger.debug("No headings found, treating as single section")
        content = raw_text.strip()
        voice_dir = _extract_voice_direction(content)
        sections.append(
            ScriptSection(
                heading="Narration",
                content=_clean_content(content),
                voice_direction=voice_dir,
            )
        )
    else:
        for i, match in enumerate(matches):
            heading = match.group(1).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
            content = raw_text[start:end].strip()

            if not content:
                continue

            voice_dir = _extract_voice_direction(content)
            cleaned = _clean_content(content)

            sections.append(
                ScriptSection(
                    heading=heading,
                    content=cleaned,
                    voice_direction=voice_dir,
                )
            )

    # Calculate metrics
    full_text = " ".join(s.content for s in sections)
    word_count = len(full_text.split())
    estimated_seconds = int((word_count / _WORDS_PER_MINUTE) * 60)

    return NarrationScript(
        title=f"{style.name.title()} Story: {_title_from_sections(sections)}",
        style=style.name,
        sections=sections,
        word_count=word_count,
        estimated_duration_seconds=estimated_seconds,
    )


def _extract_voice_direction(content: str) -> Optional[str]:
    """Extract the first [bracketed] voice direction from content."""
    match = re.search(r"\[([^\]]+)\]", content)
    if match:
        return match.group(1)
    return None


def _clean_content(content: str) -> str:
    """Remove markdown formatting artifacts from spoken content."""
    # Remove bold/italic markers
    content = re.sub(r"\*\*([^*]+)\*\*", r"\1", content)
    content = re.sub(r"\*([^*]+)\*", r"\1", content)
    content = re.sub(r"__([^_]+)__", r"\1", content)
    content = re.sub(r"_([^_]+)_", r"\1", content)
    # Remove inline code backticks
    content = re.sub(r"`([^`]+)`", r"\1", content)
    # Remove code blocks
    content = re.sub(r"```[\s\S]*?```", "", content)
    # Clean up extra whitespace
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def _title_from_sections(sections: list[ScriptSection]) -> str:
    """Derive a title from the first section heading."""
    if sections:
        return sections[0].heading
    return "Repository"
