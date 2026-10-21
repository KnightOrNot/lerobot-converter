"""Convert PiPER-X/GELLO raw sessions into LeRobot Dataset v3."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .configuration import Config, load_config
from .converter import ConversionError, convert_session


def _parser(config: Config | None = None) -> argparse.ArgumentParser:
    config = config or load_config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path, help="raw session directory")
    parser.add_argument("output", type=Path, help="new LeRobot dataset directory")
    parser.add_argument(
        "--config",
        type=Path,
        help="TOML defaults file (default: <repository>/config/default.toml)",
    )
    parser.add_argument(
        "--repo-id",
        default=config.conversion.repo_id or None,
        help="LeRobot repository id; defaults to local/<session-directory-name>",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=config.conversion.fps,
        help="target dataset FPS",
    )
    parser.add_argument(
        "--without-velocity",
        action="store_true",
        default=config.conversion.without_velocity,
        help="omit observation.velocity",
    )
    parser.add_argument(
        "--without-ee-pose",
        action="store_true",
        default=config.conversion.without_ee_pose,
        help="omit observation.ee_pose",
    )
    return parser


def _config_path(argv: Sequence[str]) -> Path | None:
    for index, value in enumerate(argv):
        if value == "--config" and index + 1 < len(argv):
            return Path(argv[index + 1])
        if value.startswith("--config="):
            return Path(value.split("=", 1)[1])
    return None


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        config = load_config(_config_path(arguments))
    except (OSError, ValueError, TypeError) as exc:
        print(f"lerobot-converter: invalid configuration: {exc}", file=sys.stderr)
        return 1
    args = _parser(config).parse_args(arguments)
    try:
        report = convert_session(
            args.session,
            args.output,
            repo_id=args.repo_id or f"local/{args.session.name}",
            fps=args.fps,
            include_velocity=not args.without_velocity,
            include_ee_pose=not args.without_ee_pose,
        )
    except (ConversionError, OSError, ValueError) as exc:
        print(f"lerobot-converter: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 0


__all__ = ["ConversionError", "convert_session", "main"]
