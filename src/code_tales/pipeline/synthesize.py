"""ElevenLabs TTS integration for audio synthesis."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx

from ..config import CodeTalesConfig
from ..models import NarrationScript, StyleConfig

logger = logging.getLogger(__name__)

_ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
_PAUSE_BETWEEN_SECTIONS = "\n\n"  # Natural paragraph break for TTS
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0


def synthesize_audio(
    script: NarrationScript,
    style: StyleConfig,
    output_path: Path,
    config: CodeTalesConfig,
) -> Path:
    """Convert a narration script to audio using ElevenLabs TTS.

    If no ElevenLabs API key is configured, falls back to text-only output.

    Args:
        script: The narration script to synthesize.
        style: Style configuration including voice_id and voice_params.
        output_path: Where to save the audio file (mp3).
        config: Pipeline configuration.

    Returns:
        Path to the saved audio file, or text file if no TTS key available.
    """
    # Always save the text version
    text_path = output_path.with_suffix(".md")
    save_text_output(script, text_path)

    if not config.elevenlabs_api_key:
        logger.warning(
            "No ELEVENLABS_API_KEY configured. Saving text-only output to %s", text_path
        )
        return text_path

    logger.info(
        "Synthesizing audio with voice_id=%s, output=%s", style.voice_id, output_path
    )

    # Combine all sections into one text blob with natural pauses
    full_text = _build_tts_text(script)

    try:
        audio_bytes = _call_elevenlabs(
            text=full_text,
            voice_id=style.voice_id,
            voice_params=style.voice_params,
            api_key=config.elevenlabs_api_key,
        )
    except RuntimeError as exc:
        logger.error("TTS synthesis failed: %s — saving text output instead", exc)
        return text_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(audio_bytes)
    logger.info("Audio saved: %s (%d bytes)", output_path, len(audio_bytes))
    return output_path


def _build_tts_text(script: NarrationScript) -> str:
    """Concatenate script sections with natural pauses for TTS."""
    parts: list[str] = []
    for section in script.sections:
        # Add section heading as spoken text
        parts.append(section.heading + ".")
        parts.append(section.content)
    return _PAUSE_BETWEEN_SECTIONS.join(parts)


def _call_elevenlabs(
    text: str,
    voice_id: str,
    voice_params: dict,
    api_key: str,
) -> bytes:
    """Call the ElevenLabs Text-to-Speech API with retry logic.

    Args:
        text: The text to synthesize.
        voice_id: ElevenLabs voice ID.
        voice_params: Voice settings (stability, similarity_boost, style, etc.).
        api_key: ElevenLabs API key.

    Returns:
        Raw MP3 audio bytes.

    Raises:
        RuntimeError: If the API call fails after all retries.
    """
    url = _ELEVENLABS_TTS_URL.format(voice_id=voice_id)
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": voice_params.get("stability", 0.5),
            "similarity_boost": voice_params.get("similarity_boost", 0.75),
            "style": voice_params.get("style", 0.0),
            "use_speaker_boost": True,
        },
        "output_format": "mp3_44100_128",
    }

    last_exc: Exception = RuntimeError("Unknown error")

    for attempt in range(_MAX_RETRIES):
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                return response.content

            if response.status_code == 429:
                # Rate limited — back off
                delay = _RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "ElevenLabs rate limited (attempt %d/%d). Retrying in %.1fs...",
                    attempt + 1,
                    _MAX_RETRIES,
                    delay,
                )
                time.sleep(delay)
                last_exc = RuntimeError(f"Rate limited (HTTP 429) after {attempt + 1} attempts")
                continue

            if response.status_code == 401:
                raise RuntimeError(
                    "Invalid ElevenLabs API key. Check ELEVENLABS_API_KEY."
                )

            if response.status_code >= 500:
                delay = _RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "ElevenLabs server error %d (attempt %d/%d). Retrying in %.1fs...",
                    response.status_code,
                    attempt + 1,
                    _MAX_RETRIES,
                    delay,
                )
                time.sleep(delay)
                last_exc = RuntimeError(
                    f"ElevenLabs server error {response.status_code}: {response.text[:200]}"
                )
                continue

            raise RuntimeError(
                f"ElevenLabs API error {response.status_code}: {response.text[:200]}"
            )

        except httpx.TimeoutException as exc:
            delay = _RETRY_BASE_DELAY * (2 ** attempt)
            logger.warning(
                "ElevenLabs request timed out (attempt %d/%d). Retrying in %.1fs...",
                attempt + 1,
                _MAX_RETRIES,
                delay,
            )
            time.sleep(delay)
            last_exc = exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Network error calling ElevenLabs API: {exc}"
            ) from exc

    raise RuntimeError(f"ElevenLabs synthesis failed after {_MAX_RETRIES} attempts: {last_exc}")


def save_text_output(script: NarrationScript, output_path: Path) -> Path:
    """Save the narration script as a readable markdown file.

    Always called regardless of TTS availability.

    Args:
        script: The narration script to save.
        output_path: Path to the output markdown file.

    Returns:
        Path to the saved text file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append(f"# {script.title}\n")
    lines.append(f"**Style:** {script.style}  ")
    lines.append(f"**Word Count:** {script.word_count:,}  ")

    duration_min = script.estimated_duration_seconds // 60
    duration_sec = script.estimated_duration_seconds % 60
    lines.append(f"**Estimated Duration:** {duration_min}m {duration_sec}s\n")
    lines.append("---\n")

    for section in script.sections:
        lines.append(f"## {section.heading}\n")
        if section.voice_direction:
            lines.append(f"*[Voice direction: {section.voice_direction}]*\n")
        lines.append(section.content)
        lines.append("\n")

    text = "\n".join(lines)
    output_path.write_text(text, encoding="utf-8")
    logger.info("Text script saved: %s", output_path)
    return output_path
