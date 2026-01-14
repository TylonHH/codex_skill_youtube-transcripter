# Youtube Transcripter (Codex Skill)

A Codex skill that extracts clean YouTube transcripts from URLs or video IDs and saves
them as plain text. Designed for use inside Codex workflows with a best-effort
fallback chain so you can keep working even if one extractor is unavailable.

## Highlights

- Accepts full YouTube URLs or bare video IDs
- Auto language detection with optional forced language
- Multiple extraction backends with automatic fallback
- Cleaned, reflowed text output (VTT timestamps removed)
- Batch mode for multiple videos

## Quick Start

### Use in Codex

1. Copy this folder into your Codex skills directory:

```text
~/.codex/skills/youtube-transcripter
```

2. Restart Codex or reload skills.

3. Invoke the skill in a prompt:

```text
/skill youtube-transcripter
```

You can also discover and invoke skills by:

- Running `/skills` to list available skills
- Typing `$` and selecting `youtube-transcripter`

Codex loads skills from repo and user scopes (for example, `.codex/skills` in
your repo or `~/.codex/skills` in your home directory). If a skill name exists
in multiple scopes, the higher-precedence location wins.

### Run the script directly

```bash
python scripts/get_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

This writes a `transcript_<id>.txt` file into `transcripts/` by default.

## Installation

Python 3.9+ recommended. Install at least one of the extractors:

```bash
python -m pip install youtube-transcript-api
```

Optional fallback (recommended for robustness):

```bash
python -m pip install yt-dlp
```

If you are on Windows with Chocolatey and have an elevated shell:

```bash
choco install yt-dlp -y
```

## Usage

### Single video

```bash
python scripts/get_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Multiple videos into a folder

```bash
python scripts/get_transcript.py VIDEO_ID_1 "https://youtu.be/VIDEO_ID_2" --out-dir transcripts
```

### Force a language

```bash
python scripts/get_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID" --lang en
```

### Keep raw line breaks

```bash
python scripts/get_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID" --wrap 0
```

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `inputs` | required | One or more URLs or video IDs |
| `--lang` | `auto` | Language code like `en`, `de`, or `auto` |
| `--out` | none | Output file (single input only) |
| `--out-dir` | `transcripts` | Output directory for batch runs |
| `--wrap` | `125` | Reflow width; `0` disables reflow |

## How It Works

The extractor attempts the following in order:

1. `youtube-transcript-api` (fast, no download)
2. `yt-dlp` Python module (uses caption download)
3. `yt-dlp` binary (writes VTT, then strips timestamps)

If all fail, the tool prints a clear error with the underlying reasons.

## Output

By default:

- Single input: `transcripts/transcript_<id>.txt`
- Multiple inputs: `transcripts/transcript_<id>.txt` per video

Output is UTF-8 and cleaned of timestamps and VTT markup.

## Repository Layout

```
scripts/
  get_transcript.py   Main CLI entry
references/           Optional helper notes (if present)
SKILL.md              Skill workflow guidance
```

## Troubleshooting

- Rate limits or missing captions: try a different language or video.
- No transcript available: the video may not have captions.
- `yt-dlp` missing: install via pip or Chocolatey (Windows).

## License

MIT