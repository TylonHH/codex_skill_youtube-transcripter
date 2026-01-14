#!/usr/bin/env python
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from typing import Iterable, Optional, Sequence, Tuple


def clean_vtt(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        if "-->" in line:
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _pick_lang(preferred: str, available: Sequence[str]) -> Optional[str]:
    if preferred and preferred != "auto":
        return preferred if preferred in available else None
    for candidate in ("de", "en"):
        if candidate in available:
            return candidate
    return available[0] if available else None


def _parse_input(value: str) -> Tuple[str, str]:
    patterns = [
        r"v=([a-zA-Z0-9_-]{6,})",
        r"youtu\.be/([a-zA-Z0-9_-]{6,})",
    ]
    for pat in patterns:
        match = re.search(pat, value)
        if match:
            video_id = match.group(1)
            return video_id, f"https://www.youtube.com/watch?v={video_id}"
    if re.fullmatch(r"[a-zA-Z0-9_-]{6,}", value):
        return value, f"https://www.youtube.com/watch?v={value}"
    raise RuntimeError("Could not parse video id from input")


def _reflow_text(text: str, width: int) -> str:
    if width <= 0:
        return text
    collapsed = re.sub(r"\s+", " ", text).strip()
    if not collapsed:
        return ""
    return textwrap.fill(collapsed, width=width, break_long_words=False)


def extract_with_ytdlp(url: str, lang: str) -> str:
    if not shutil.which("yt-dlp"):
        raise RuntimeError("yt-dlp not found on PATH")
    langs = ["en", "de"] if lang == "auto" else [lang]
    last_err = None
    for use_lang in langs:
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                "yt-dlp",
                "--skip-download",
                "--write-auto-sub",
                "--sub-lang",
                use_lang,
                "--sub-format",
                "vtt",
                "--output",
                os.path.join(tmpdir, "%(id)s.%(ext)s"),
                url,
            ]
            try:
                subprocess.run(
                    cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
            except subprocess.CalledProcessError as exc:
                last_err = exc
                continue
            vtt_files = [p for p in os.listdir(tmpdir) if p.endswith(".vtt")]
            if not vtt_files:
                last_err = RuntimeError("yt-dlp did not produce a .vtt file")
                continue
            vtt_path = os.path.join(tmpdir, vtt_files[0])
            with open(vtt_path, "r", encoding="utf-8") as f:
                return clean_vtt(f.read())
    if last_err:
        raise RuntimeError(str(last_err))
    raise RuntimeError("yt-dlp did not produce a .vtt file")


def extract_with_ytdlp_module(url: str, lang: str) -> str:
    try:
        from yt_dlp import YoutubeDL  # type: ignore
    except Exception as exc:  # pragma: no cover - import check
        raise RuntimeError("yt-dlp Python module not installed") from exc
    with tempfile.TemporaryDirectory() as tmpdir:
        info_opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
        }
        with YoutubeDL(info_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        available = []
        for key in ("subtitles", "automatic_captions"):
            value = info.get(key) or {}
            available.extend(list(value.keys()))
        selected = _pick_lang(lang, available)
        if not selected:
            raise RuntimeError("No subtitles available for requested language")
        opts = {
            "skip_download": True,
            "writeautomaticsub": True,
            "writesubtitles": True,
            "subtitleslangs": [selected],
            "subtitlesformat": "vtt",
            "outtmpl": os.path.join(tmpdir, "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
        vtt_files = [p for p in os.listdir(tmpdir) if p.endswith(".vtt")]
        if not vtt_files:
            raise RuntimeError("yt-dlp module did not produce a .vtt file")
        vtt_path = os.path.join(tmpdir, vtt_files[0])
        with open(vtt_path, "r", encoding="utf-8") as f:
            return clean_vtt(f.read())


def extract_with_api(url: str, lang: str) -> str:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
    except Exception as exc:  # pragma: no cover - import check
        raise RuntimeError("youtube-transcript-api not installed") from exc
    video_id, _ = _parse_input(url)
    api = YouTubeTranscriptApi()
    if lang == "auto":
        available = [t.language_code for t in api.list(video_id)]
        selected = _pick_lang(lang, available)
        if not selected:
            raise RuntimeError("No transcripts available via API")
        use_langs: Iterable[str] = [selected]
    else:
        use_langs = [lang]
    transcript = api.fetch(video_id, languages=use_langs)
    if hasattr(transcript, "to_raw_data"):
        data = transcript.to_raw_data()
    elif isinstance(transcript, list):
        data = transcript
    else:
        data = list(transcript)
    lines = []
    for item in data:
        if isinstance(item, dict):
            text = item.get("text", "")
        else:
            text = getattr(item, "text", "")
        if text:
            lines.append(text)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract YouTube transcript text from a URL."
    )
    parser.add_argument("inputs", nargs="+", help="YouTube URL(s) or video ID(s)")
    parser.add_argument(
        "--lang",
        default="auto",
        help="Transcript language code (e.g. en, de) or auto",
    )
    parser.add_argument("--out", help="Output text file (single input only)")
    parser.add_argument(
        "--out-dir",
        default="transcripts",
        help="Output directory for multiple inputs (default: current directory)",
    )
    parser.add_argument(
        "--wrap",
        type=int,
        default=125,
        help="Reflow transcript to this line width (0 to disable)",
    )
    args = parser.parse_args()

    if args.out and len(args.inputs) > 1:
        sys.stderr.write("--out can only be used with a single input.\n")
        return 2

    failures = 0
    os.makedirs(args.out_dir, exist_ok=True)

    for value in args.inputs:
        try:
            video_id, url = _parse_input(value)
        except Exception as exc:
            sys.stderr.write(f"Failed to parse input '{value}': {exc}\n")
            failures += 1
            continue

        errors = []
        try:
            text = extract_with_api(url, args.lang)
        except Exception as exc:
            errors.append(str(exc))
            try:
                text = extract_with_ytdlp_module(url, args.lang)
            except Exception as exc2:
                errors.append(str(exc2))
                try:
                    text = extract_with_ytdlp(url, args.lang)
                except Exception as exc3:
                    errors.append(str(exc3))
                    sys.stderr.write("Failed to extract transcript.\n")
                    for err in errors:
                        sys.stderr.write(f"- {err}\n")
                    sys.stderr.write(
                        "Install youtube-transcript-api or yt-dlp, "
                        "or provide transcript text manually.\n"
                    )
                    failures += 1
                    continue

        if args.out:
            out_path = args.out
        else:
            filename = f"transcript_{video_id}.txt"
            out_path = os.path.join(args.out_dir, filename)

        text = _reflow_text(text, args.wrap)

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
