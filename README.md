# code-tales

[![Featured in Agentic Development Blog — Post #9](https://img.shields.io/badge/Agentic%20Development%20Blog-Post%20%239-blue)](https://github.com/krzemienski/agentic-development-guide)

## Related Post

**Featured in the Agentic Development Blog series — Post #9: From GitHub Repos to Audio Stories**

- Send date: Mon Jun 8, 2026
- LinkedIn: _link added on send day_
- Canonical blog post: https://ai.hack.ski/blog/<slug-set-on-send-day>
- Series hub: [agentic-development-guide](https://github.com/krzemienski/agentic-development-guide)

---


[![PyPI version](https://img.shields.io/pypi/v/code-tales.svg)](https://pypi.org/project/code-tales/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Transform any GitHub repository into a narrated audio story.**

`code-tales` clones a repository, analyzes its structure, generates a narration script with Claude AI, and synthesizes speech with ElevenLabs TTS — in 9 distinctive narrative styles.

```
GitHub URL → Clone → Analyze → Narrate (Claude) → Synthesize (ElevenLabs) → Audio Story
```

---

## Quick Start

```bash
pip install code-tales

# Set API keys
export ANTHROPIC_API_KEY=sk-ant-...
export ELEVENLABS_API_KEY=...        # Optional — text output still works without it

# Generate an audio story
code-tales generate --repo https://github.com/tiangolo/fastapi --style documentary

# Preview the script (no audio)
code-tales preview --repo https://github.com/pallets/flask --style podcast

# List all styles
code-tales list-styles
```

---

## Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    code-tales pipeline                          │
├──────────┬──────────┬──────────────┬──────────────┬────────────┤
│  Input   │  Clone   │   Analyze    │   Narrate    │ Synthesize │
│          │          │              │              │            │
│ GitHub   │ gitpython│ Languages    │ Claude API   │ ElevenLabs │
│ URL  or  │ shallow  │ Dependencies │ claude-      │ TTS API    │
│ Local    │ clone    │ Frameworks   │ sonnet-4-6   │ 9 voices   │
│ Path     │ depth=1  │ Patterns     │ streaming    │ mp3 output │
│          │          │ Key files    │              │            │
└──────────┴──────────┴──────────────┴──────────────┴────────────┘
         Output: script.md + story.mp3
```

---

## Style Showcase

| Style | Description | Best For |
|-------|-------------|----------|
| `documentary` | David Attenborough observes code as a living ecosystem | Any project |
| `fiction` | Literary drama with characters, conflict, and arc | OSS projects |
| `tutorial` | Friendly educational walkthrough step-by-step | Libraries/SDKs |
| `podcast` | Casual tech podcast episode with hot takes | Developer tools |
| `technical` | Dense engineering review for practitioners | Architecture evaluation |
| `debate` | Structured argument for and against design decisions | Controversial choices |
| `interview` | Q&A with an expert about the codebase | Deep-dive learning |
| `executive` | Crisp briefing for technical leadership | Adoption decisions |
| `storytelling` | Hero's journey — the epic quest to solve a problem | Inspiring projects |

---

## Installation

```bash
# Core (text output only)
pip install code-tales

# With TTS audio synthesis
pip install "code-tales[tts]"
```

---

## API Keys Setup

### Required: Anthropic (Claude AI)

```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Get a key at [console.anthropic.com](https://console.anthropic.com).

### Optional: ElevenLabs (TTS Audio)

```bash
export ELEVENLABS_API_KEY=your-key-here
```

Get a key at [elevenlabs.io](https://elevenlabs.io). Without this key, `code-tales`
still generates a full markdown script — just no `.mp3` audio file.

---

## CLI Reference

### `generate` — Full Pipeline

```bash
code-tales generate [OPTIONS]

Options:
  --repo URL          GitHub repository URL
  --path PATH         Local git repository path
  --style NAME        Narrative style (required). See list-styles.
  --output DIR        Output directory [default: ./output/]
  --no-audio          Generate text script only, skip TTS
  --verbose / -v      Enable debug logging
```

Examples:

```bash
# GitHub URL
code-tales generate --repo https://github.com/django/django --style executive

# Local repo
code-tales generate --path ./my-project --style storytelling --output ./stories/

# Text only (no ElevenLabs key needed)
code-tales generate --repo https://github.com/rust-lang/rust --style technical --no-audio
```

### `preview` — Script Only

```bash
code-tales preview [OPTIONS]

Options:
  --repo URL      GitHub repository URL
  --path PATH     Local git repository path
  --style NAME    Narrative style (required)
```

### `list-styles` — Browse Styles

```bash
code-tales list-styles
```

---

## Python API

```python
from code_tales import CodeTalesPipeline, CodeTalesConfig
from pathlib import Path

# Initialize
config = CodeTalesConfig.from_env()
pipeline = CodeTalesPipeline(config=config)

# Generate full story
result = pipeline.generate(
    repo_url_or_path="https://github.com/tiangolo/fastapi",
    style_name="documentary",
    output_dir=Path("./output"),
)

print(f"Script: {result.text_path}")
print(f"Audio:  {result.audio_path}")
print(f"Words:  {result.script.word_count}")

# Preview script only
script = pipeline.preview(
    repo_url_or_path="https://github.com/pallets/flask",
    style_name="podcast",
)

for section in script.sections:
    print(f"\n## {section.heading}")
    print(section.content[:200] + "...")
```

---

## Configuration

All configuration can be set via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Anthropic API key (required) |
| `ELEVENLABS_API_KEY` | — | ElevenLabs API key (optional) |
| `CODE_TALES_OUTPUT_DIR` | `./output` | Output directory |
| `CODE_TALES_TEMP_DIR` | `/tmp/code-tales` | Temp directory for clones |
| `CODE_TALES_CLONE_DEPTH` | `1` | Git clone depth |
| `CODE_TALES_MAX_FILES` | `100` | Max files to analyze |
| `CODE_TALES_MAX_FILE_SIZE` | `100000` | Max file size in bytes |
| `CODE_TALES_CLAUDE_MODEL` | `claude-sonnet-4-6` | Claude model to use |
| `CODE_TALES_MAX_TOKENS` | `4096` | Max script tokens |

Or configure in Python:

```python
from code_tales import CodeTalesConfig, CodeTalesPipeline
from pathlib import Path

config = CodeTalesConfig(
    anthropic_api_key="sk-ant-...",
    elevenlabs_api_key="...",
    output_dir=Path("./my-stories"),
    claude_model="claude-opus-4-6",
    max_script_tokens=8192,
)
pipeline = CodeTalesPipeline(config=config)
```

---

## Custom Styles

Create your own narrative style with a YAML file:

```yaml
# my-style.yaml
name: noir
description: Hard-boiled detective investigates the codebase
tone: Cynical, world-weary, poetic — treat bugs as suspects
structure_template: |
  ## {repo_name}: A Case File

  ## The Scene
  First impressions of the codebase.

  ## The Evidence
  What the code reveals.

  ## The Verdict
  Final assessment.

voice_id: "2EiwWnXFnvU5JabPnv8n"  # ElevenLabs voice ID
voice_params:
  stability: 0.6
  similarity_boost: 0.75
  style: 0.4
example_opener: |
  It was a dark and stormy deployment...
```

Load it in Python:

```python
from code_tales.styles.registry import get_registry
from pathlib import Path

registry = get_registry()
registry.load_custom_style(Path("./my-style.yaml"))

pipeline.generate("https://github.com/owner/repo", style_name="noir")
```

See `examples/custom-style.yaml` for a fully commented example.

---

## Architecture

The pipeline is modular and each stage is independently importable:

```
src/code_tales/
├── cli.py              — Click CLI (generate, preview, list-styles)
├── config.py           — Configuration (env vars, defaults)
├── models.py           — Pydantic data models
├── pipeline/
│   ├── clone.py        — Git clone + directory tree analysis
│   ├── analyze.py      — Language, dependency, framework detection
│   ├── narrate.py      — Claude API script generation
│   ├── synthesize.py   — ElevenLabs TTS integration
│   └── orchestrate.py  — Full pipeline with Rich progress display
└── styles/
    ├── registry.py     — Style loading and lookup
    └── *.yaml          — 9 built-in style definitions
```

### Key Design Decisions

- **Shallow clones** (`depth=1`) minimize network usage and storage
- **Streaming Claude API** prevents HTTP timeouts on long scripts
- **Text output always generated** — ElevenLabs is optional
- **Style configs as YAML** — trivially extensible without code changes
- **Rich progress bars** — transparent pipeline execution
- **Pydantic v2 models** — strict validation throughout

---

## Examples

See `examples/` for:
- `sample-output/README.md` — A full generated script in documentary style
- `custom-style.yaml` — Annotated custom style with noir detective theme

---

## Built With

- **[Claude AI](https://anthropic.com)** — Script generation via `claude-sonnet-4-6`
- **[ElevenLabs](https://elevenlabs.io)** — High-quality text-to-speech synthesis
- **[GitPython](https://gitpython.readthedocs.io)** — Repository cloning
- **[Rich](https://rich.readthedocs.io)** — Terminal UI and progress display
- **[Pydantic](https://docs.pydantic.dev)** — Data validation and models
- **[Click](https://click.palletsprojects.com)** — CLI framework

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/new-style`)
3. Add your changes
4. Submit a pull request

To add a new style, create a YAML file in `src/code_tales/styles/` following the
existing format. See the [Style Showcase](#style-showcase) for examples.

---

## Troubleshooting

### `ANTHROPIC_API_KEY` not set
Set the environment variable: `export ANTHROPIC_API_KEY=sk-ant-...`. The `generate` command requires a valid Anthropic API key.

### `code-tales generate` fails with git errors
Ensure the target repository path is a valid git repository with at least one commit. The tool uses GitPython to read commit history.

### Audio generation fails
Audio synthesis requires `ELEVENLABS_API_KEY`. If not set, use `preview` mode to generate the script without audio: `code-tales preview /path/to/repo`.

### `--config` option has no effect
The `--config` CLI option is declared but not yet implemented. Use environment variables for configuration instead.

### Style not found
Use `code-tales list-styles` to see all 9 available styles. Style names are case-sensitive and must match exactly.

## License

MIT License — see [LICENSE](LICENSE) for details.

Copyright 2024 krzemienski
