#!/usr/bin/env python3
"""Batch transcode a master file to platform presets.

Usage:
    python3 transcode.py master.mov --out out/ --presets youtube,reels,twitter

Every preset encodes from the master, never from another preset's output.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PRESETS = {
    "youtube": {"scale": 1080, "vb": "8000k", "maxrate": "8560k", "ab": "384k"},
    "reels": {"scale": 1920, "vb": "4500k", "maxrate": "4800k", "ab": "128k"},
    "tiktok": {"scale": 1920, "vb": "10000k", "maxrate": "10700k", "ab": "128k"},
    "twitter": {"scale": 720, "vb": "5000k", "maxrate": "5350k", "ab": "128k"},
    "linkedin": {"scale": 720, "vb": "4500k", "maxrate": "4800k", "ab": "128k"},
    "web": {"scale": 720, "vb": "3000k", "maxrate": "3200k", "ab": "128k"},
    "whatsapp": {"scale": 720, "vb": "1200k", "maxrate": "1280k", "ab": "96k"},
}


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def verify(path: Path, expect_height: int | None = None,
           expect_duration: float | None = None) -> list[str]:
    """Return a list of problems. An empty list means the output is good."""
    problems: list[str] = []

    if not path.exists():
        return ["file does not exist"]
    if path.stat().st_size == 0:
        return ["file is empty"]

    data = probe(path)
    streams = data.get("streams", [])
    video = next((s for s in streams if s["codec_type"] == "video"), None)
    audio = next((s for s in streams if s["codec_type"] == "audio"), None)

    if video is None:
        problems.append("no video stream")
    else:
        if video.get("pix_fmt") not in ("yuv420p", "yuvj420p"):
            problems.append(f"pix_fmt {video.get('pix_fmt')} will not play in browsers")
        if expect_height and video.get("height") != expect_height:
            problems.append(f"height {video.get('height')} != {expect_height}")

    if audio is None:
        problems.append("no audio stream")

    duration = float(data.get("format", {}).get("duration", 0))
    if expect_duration and abs(duration - expect_duration) > 0.5:
        problems.append(f"duration {duration:.2f}s != expected {expect_duration:.2f}s")

    return problems


def transcode(master: Path, out_dir: Path, preset: str, settings: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{preset}.mp4"

    # Vertical presets need the 9:16 crop; landscape ones just fit the frame.
    if settings["scale"] == 1920:
        vf = ("scale=1080:1920:force_original_aspect_ratio=increase,"
              "crop=1080:1920")
    else:
        vf = f"scale=-2:{settings['scale']}"

    cmd = [
        "ffmpeg", "-y", "-i", str(master),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "slow",
        "-b:v", settings["vb"],
        "-maxrate", settings["maxrate"],
        "-bufsize", settings["maxrate"],
        "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-level", "4.0",
        "-c:a", "aac", "-b:a", settings["ab"], "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        str(out),
    ]

    subprocess.run(cmd, check=True)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("master", type=Path)
    parser.add_argument("--out", type=Path, default=Path("out"))
    parser.add_argument("--presets", default="youtube,reels,twitter")
    parser.add_argument("--skip-verify", action="store_true")
    args = parser.parse_args()

    if not args.master.exists():
        print(f"Master not found: {args.master}", file=sys.stderr)
        return 1

    names = [p.strip() for p in args.presets.split(",") if p.strip()]
    unknown = [p for p in names if p not in PRESETS]
    if unknown:
        print(f"Unknown presets: {', '.join(unknown)}", file=sys.stderr)
        print(f"Available: {', '.join(sorted(PRESETS))}", file=sys.stderr)
        return 1

    source_duration = float(
        probe(args.master).get("format", {}).get("duration", 0)
    )

    failures = 0
    for name in names:
        settings = PRESETS[name]
        print(f"→ {name} ...", flush=True)
        try:
            out = transcode(args.master, args.out, name, settings)
        except subprocess.CalledProcessError as exc:
            print(f"  FAILED (ffmpeg exit {exc.returncode})", file=sys.stderr)
            failures += 1
            continue

        size_mb = out.stat().st_size / 1e6
        print(f"  {out} ({size_mb:.1f} MB)")

        if not args.skip_verify:
            problems = verify(out, expect_duration=source_duration)
            if problems:
                print(f"  VERIFY FAILED: {'; '.join(problems)}", file=sys.stderr)
                failures += 1
            else:
                print("  verified")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
