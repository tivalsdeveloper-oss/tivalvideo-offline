"""Command-line interface."""

from __future__ import annotations

import argparse
from pathlib import Path

from .maker import VideoConfig, VideoMaker
from .tools import ToolManager


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="tivalvideo", description="Create narrated videos offline")
    commands = root.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("setup", help="download the voice model for offline use")
    setup.add_argument("--force", action="store_true", help="download the voice again")
    create = commands.add_parser("create", help="create a narrated video")
    create.add_argument("images", nargs="+", help="ordered image files")
    create.add_argument("-n", "--narration", required=True, help="text file containing narration")
    create.add_argument("-o", "--output", default="video.mp4")
    create.add_argument("--landscape", action="store_true", help="use 1920x1080 instead of 1080x1920")
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "setup":
            ToolManager().setup(force=args.force)
        else:
            text = Path(args.narration).read_text(encoding="utf-8")
            config = VideoConfig.landscape() if args.landscape else VideoConfig.shorts()
            VideoMaker(config).create(args.images, text, args.output)
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI converts failures into readable messages
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
