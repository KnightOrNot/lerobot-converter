"""Convert PiPER-X/GELLO raw sessions into LeRobot Dataset v3."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .converter import ConversionError, convert_session


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path, help="raw session directory")
    parser.add_argument("output", type=Path, help="new LeRobot dataset directory")
    parser.add_argument(
        "--repo-id",
        help="LeRobot repository id; defaults to local/<session-directory-name>",
    )
    parser.add_argument("--fps", type=int, default=30, help="target dataset FPS")
    parser.add_argument(
        "--without-velocity",
        action="store_true",
        help="omit observation.velocity",
    )
    parser.add_argument(
        "--without-ee-pose",
        action="store_true",
        help="omit observation.ee_pose",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
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
