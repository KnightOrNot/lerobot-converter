"""Validate raw RGB streams and match them to the dataset's common timeline."""

from __future__ import annotations

import bisect
import json
import math
import re
from pathlib import Path
from typing import Any


def camera_specs(manifest: dict[str, Any], error: type[Exception]) -> dict[str, Any]:
    cameras = manifest.get("cameras", {})
    if manifest["format_version"] == 1:
        if cameras:
            raise error("camera sessions must declare raw format_version 2")
        return {}
    if not isinstance(cameras, dict) or not cameras:
        raise error("raw v2 must declare non-empty cameras")
    for name, spec in cameras.items():
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) or not isinstance(
            spec, dict
        ):
            raise error("invalid camera name or specification")
        if spec.get("clock") != "time.monotonic_ns" or spec.get("storage") not in {
            "rgb8_png",
            "z16_png",
        }:
            raise error(f"{name}: camera must use host monotonic clock and PNG storage")
        for key in ("width", "height", "fps"):
            if type(spec.get(key)) is not int or spec[key] <= 0:
                raise error(f"{name}: {key} must be a positive integer")
        kind = spec.get("kind", "color")
        if kind not in {"color", "depth"} or spec["storage"] != (
            "z16_png" if kind == "depth" else "rgb8_png"
        ):
            raise error(f"{name}: camera kind and storage disagree")
        if kind == "depth":
            units = spec.get("depth_units_m")
            if (
                type(units) not in (int, float)
                or not math.isfinite(units)
                or units <= 0
            ):
                raise error(f"{name}: depth_units_m must be positive and finite")
        skew = spec.get("max_skew_ms")
        if type(skew) not in (int, float) or not math.isfinite(skew) or skew <= 0:
            raise error(f"{name}: max_skew_ms must be positive and finite")
    return cameras


def align_images(
    session: Path,
    episode: str,
    specs: dict[str, Any],
    *,
    start_ns: int,
    count: int,
    fps: int,
    max_skew_ms: float | None,
    error: type[Exception],
) -> tuple[dict[str, tuple[Path, ...]], dict[str, Any]]:
    from PIL import Image

    selected, quality = {}, {}
    for name, spec in specs.items():
        folder = session / "cameras" / name / episode
        index = folder / "frames.jsonl"
        if not index.is_file():
            raise error(f"missing camera index: {index}")
        timestamps, paths, seen = [], [], set()
        previous_number, previous_offset, missing = None, None, 0
        with index.open(encoding="utf-8") as stream:
            for sequence, line in enumerate(stream):
                location = f"{index}:{sequence + 1}"
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise error(f"{location}: invalid camera JSON") from exc
                if (
                    not isinstance(row, dict)
                    or type(row.get("frame_index")) is not int
                    or row["frame_index"] != sequence
                ):
                    raise error(
                        f"{location}: camera frame_index must be continuous from zero"
                    )
                timestamp = row.get("timestamp_ns")
                if type(timestamp) is not int or timestamp < 0:
                    raise error(
                        f"{location}: timestamp_ns must be a non-negative integer"
                    )
                if timestamps and timestamp <= timestamps[-1]:
                    raise error(
                        f"{location}: camera timestamps must be strictly increasing"
                    )
                if row.get("sdk_timestamp_domain") not in {
                    "global_time",
                    "system_time",
                }:
                    raise error(f"{location}: camera timestamp is not host-aligned")
                for key in ("received_time_ns", "frame_number", "clock_uncertainty_ns"):
                    if type(row.get(key)) is not int or row[key] < 0:
                        raise error(f"{location}: invalid camera {key}")
                sdk_time, offset = (
                    row.get("sdk_timestamp_ms"),
                    row.get("clock_offset_ns"),
                )
                if (
                    type(sdk_time) not in (int, float)
                    or not math.isfinite(sdk_time)
                    or sdk_time < 0
                    or type(offset) is not int
                ):
                    raise error(f"{location}: invalid SDK clock bridge")
                if abs(timestamp - (round(sdk_time * 1e6) + offset)) > 1:
                    raise error(
                        f"{location}: camera clock bridge does not match timestamp_ns"
                    )
                if (
                    row["clock_uncertainty_ns"] > 5_000_000
                    or not -50_000_000
                    <= row["received_time_ns"] - timestamp
                    <= 1_000_000_000
                ):
                    raise error(
                        f"{location}: camera timestamp is outside host clock bounds"
                    )
                if previous_number is not None:
                    if row["frame_number"] <= previous_number:
                        raise error(f"{location}: SDK frame number is not increasing")
                    missing += row["frame_number"] - previous_number - 1
                if (
                    previous_offset is not None
                    and abs(offset - previous_offset) > 5_000_000
                ):
                    raise error(f"{location}: host clock offset stepped")
                previous_number, previous_offset = row["frame_number"], offset
                relative = row.get("file")
                if not isinstance(relative, str) or Path(relative).is_absolute():
                    raise error(f"{location}: invalid camera image path")
                path = (folder / relative).resolve()
                if not path.is_relative_to(folder.resolve()) or path in seen:
                    raise error(
                        f"{location}: camera image escapes folder or is duplicated"
                    )
                try:
                    with Image.open(path) as image:
                        if (
                            image.mode
                            not in (
                                {"I;16", "I;16B", "I"}
                                if spec.get("kind") == "depth"
                                else {"RGB"}
                            )
                            or image.size != (spec["width"], spec["height"])
                            or image.format != "PNG"
                        ):
                            raise error(
                                f"{location}: image must be declared-size RGB or Z16 PNG"
                            )
                        image.verify()
                except (OSError, ValueError) as exc:
                    raise error(f"{location}: invalid image {path}: {exc}") from exc
                paths.append(path)
                seen.add(path)
                timestamps.append(timestamp)
        if not timestamps:
            raise error(f"empty camera index: {index}")
        chosen, errors = [], []
        tolerance = spec["max_skew_ms"] if max_skew_ms is None else max_skew_ms
        for frame_index in range(count):
            target = start_ns + frame_index * 1_000_000_000 / fps
            right = bisect.bisect_left(timestamps, target)
            candidates = [i for i in (right - 1, right) if 0 <= i < len(timestamps)]
            nearest = min(candidates, key=lambda i: (abs(timestamps[i] - target), i))
            mismatch = abs(timestamps[nearest] - target) / 1_000_000
            if mismatch > tolerance:
                raise error(
                    f"{name}/{episode}: camera matching error {mismatch:.3f} ms exceeds {tolerance:g} ms at output frame {frame_index}"
                )
            chosen.append(nearest)
            errors.append(mismatch)
        selected[name] = tuple(paths[i] for i in chosen)
        quality[name] = {
            "raw_frames": len(paths),
            "sdk_missing_frames": missing,
            "converted_frames": len(chosen),
            "unique_frames": len(set(chosen)),
            "repeated_frames": len(chosen) - len(set(chosen)),
            "max_time_match_error_ms": max(errors),
            "mean_time_match_error_ms": sum(errors) / len(errors),
            "max_allowed_skew_ms": tolerance,
        }
    return selected, quality
