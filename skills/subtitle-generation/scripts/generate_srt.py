#!/usr/bin/env python3
"""Generate an SRT from a faster-whisper transcript, with caption-quality
post-processing: line breaking, reading-speed enforcement, and minimum
durations.

Usage:
    python3 generate_srt.py audio.wav -o out.srt
"""
from __future__ import annotations

import argparse
import re
import sys
import wave
from pathlib import Path

MAX_CHARS_PER_LINE = 42
MAX_LINES = 2
MIN_DURATION = 1.0
MAX_DURATION = 7.0
MIN_GAP = 0.08
MAX_CPS = 17.0


def split_caption(text: str, max_chars: int = MAX_CHARS_PER_LINE,
                  max_lines: int = MAX_LINES) -> list[str]:
    """Break text into lines that fit the character budget."""
    words = text.split()
    lines: list[str] = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines[:max_lines]


def cps(text: str, start: float, end: float) -> float:
    """Characters per second, excluding spaces."""
    return len(text.replace(" ", "")) / max(end - start, 0.001)


def retime(text: str, start: float, end: float) -> tuple[float, float]:
    """Extend the duration when the reading speed is too fast."""
    chars = len(text.replace(" ", ""))
    needed = chars / MAX_CPS
    if end - start < needed:
        end = start + needed
    if end - start < MIN_DURATION:
        end = start + MIN_DURATION
    if end - start > MAX_DURATION:
        end = start + MAX_DURATION
    return start, end


def timestamp(seconds: float) -> str:
    ms = int(round((seconds % 1) * 1000))
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if ms == 1000:
        ms = 0
        s += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe(audio: str, model_size: str = "large-v3",
               device: str = "cuda") -> list[dict]:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("faster-whisper is not installed: pip install faster-whisper",
              file=sys.stderr)
        raise SystemExit(1)

    model = WhisperModel(model_size, device=device,
                         compute_type="float16" if device == "cuda" else "int8")

    segments, _ = model.transcribe(
        audio,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        word_timestamps=True,
    )

    return [
        {"start": s.start, "end": s.end, "text": s.text.strip()}
        for s in segments
    ]


def build_captions(segments: list[dict]) -> list[dict]:
    """Turn segments into caption entries with enforced timing."""
    captions: list[dict] = []

    for seg in segments:
        start, end = retime(seg["text"], seg["start"], seg["end"])
        lines = split_caption(seg["text"])

        # A cue that still does not fit gets split into two.
        if len(lines) == MAX_LINES and len("\n".join(lines)) > MAX_CHARS_PER_LINE * 2:
            mid = (start + end) / 2
            words = seg["text"].split()
            half = len(words) // 2
            captions.append({"start": start, "end": mid,
                             "text": " ".join(words[:half])})
            captions.append({"start": mid, "end": end,
                             "text": " ".join(words[half:])})
        else:
            captions.append({"start": start, "end": end, "text": "\n".join(lines)})

    # Enforce the minimum gap between cues.
    for i in range(1, len(captions)):
        prev = captions[i - 1]
        if captions[i]["start"] < prev["end"] + MIN_GAP:
            prev["end"] = max(prev["start"] + 0.2,
                              captions[i]["start"] - MIN_GAP)

    return captions


def to_srt(captions: list[dict]) -> str:
    blocks = []
    for i, cap in enumerate(captions, 1):
        blocks.append(
            f"{i}\n"
            f"{timestamp(cap['start'])} --> {timestamp(cap['end'])}\n"
            f"{cap['text']}"
        )
    return "\n\n".join(blocks) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio")
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--report", action="store_true",
                        help="Print reading-speed diagnostics")
    args = parser.parse_args()

    segments = transcribe(args.audio, args.model, args.device)
    captions = build_captions(segments)
    srt = to_srt(captions)

    if args.output:
        args.output.write_text(srt, encoding="utf-8")
        print(f"wrote {args.output} ({len(captions)} cues)")
    else:
        sys.stdout.write(srt)

    if args.report:
        slow = [c for c in captions
                if cps(c["text"], c["start"], c["end"]) > MAX_CPS]
        print(f"cues over {MAX_CPS} cps: {len(slow)}/{len(captions)}",
              file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
