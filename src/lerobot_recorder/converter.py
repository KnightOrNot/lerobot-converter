"""Validation, resampling, and LeRobot Dataset v3 writing."""

from __future__ import annotations

import bisect
import json
import math
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any, Protocol


class ConversionError(RuntimeError):
    """Raised when raw data cannot be converted without hiding corruption."""


class DatasetProtocol(Protocol):
    def add_frame(self, frame: dict[str, Any]) -> None: ...

    def save_episode(self) -> None: ...

    def finalize(self) -> None: ...


@dataclass(frozen=True)
class EpisodeQuality:
    source: str
    raw_samples: int
    converted_frames: int
    duration_s: float
    actual_sample_hz: float
    average_interval_ms: float
    max_interval_ms: float
    missing_sequences: int
    duplicate_sequences: int
    dimension_errors: int
    non_finite_errors: int
    max_time_match_error_ms: float


@dataclass(frozen=True)
class ConversionReport:
    source_session: str
    output_root: str
    repo_id: str
    target_fps: int
    raw_samples: int
    converted_frames: int
    kept_episodes: int
    ignored_partial_episodes: int
    failed_episodes: int
    episodes: tuple[EpisodeQuality, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PreparedEpisode:
    source: Path
    frames: tuple[dict[str, Any], ...]
    quality: EpisodeQuality


_VECTOR_SIZES = {
    "action": 7,
    "joint_positions": 7,
    "joint_velocities": 7,
    "ee_pos_quat": 7,
}
_INTEGER_FIELDS = (
    "sequence",
    "command_time_ns",
    "observation_time_ns",
    "wall_time_ns",
    "control_period_ns",
)
_REQUIRED_MANIFEST = {
    "format": "piper_x_gello_raw",
    "format_version": 1,
    "clock": "time.monotonic_ns",
    "robot_type": "piper_x",
    "joint_units": "rad",
    "velocity_units": "rad/s",
    "position_units": "m",
    "quaternion_order": "xyzw",
}


def _read_manifest(session: Path) -> dict[str, Any]:
    path = session / "manifest.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConversionError(f"manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConversionError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConversionError(f"manifest must be a JSON object: {path}")
    for key, expected in _REQUIRED_MANIFEST.items():
        if value.get(key) != expected:
            raise ConversionError(
                f"manifest field {key!r} must be {expected!r}, got {value.get(key)!r}"
            )
    if not isinstance(value.get("task"), str) or not value["task"].strip():
        raise ConversionError("manifest task must be a non-empty string")
    names = value.get("joint_names")
    if (
        not isinstance(names, list)
        or len(names) != 7
        or not all(isinstance(name, str) and name for name in names)
    ):
        raise ConversionError("manifest joint_names must contain seven names")
    control_hz = value.get("control_hz")
    if (
        not isinstance(control_hz, (int, float))
        or not math.isfinite(control_hz)
        or control_hz <= 0
    ):
        raise ConversionError("manifest control_hz must be positive and finite")
    if value.get("gripper_range") != [0.0, 1.0]:
        raise ConversionError("manifest gripper_range must be [0.0, 1.0]")
    return value


def _finite_vector(value: Any, size: int, field: str, location: str) -> list[float]:
    if not isinstance(value, list) or len(value) != size:
        raise ConversionError(f"{location}: {field} must be a {size}-element list")
    result: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ConversionError(f"{location}: {field} contains a non-number")
        number = float(item)
        if not math.isfinite(number):
            raise ConversionError(f"{location}: {field} contains NaN or Inf")
        result.append(number)
    return result


def _validate_frame(
    value: Any, *, location: str, expected_sequence: int
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConversionError(f"{location}: frame must be a JSON object")
    frame = dict(value)
    for field in _INTEGER_FIELDS:
        item = frame.get(field)
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise ConversionError(f"{location}: {field} must be a non-negative integer")
    if frame["sequence"] != expected_sequence:
        raise ConversionError(
            f"{location}: expected sequence {expected_sequence}, got {frame['sequence']}"
        )
    for field, size in _VECTOR_SIZES.items():
        frame[field] = _finite_vector(frame.get(field), size, field, location)
    gripper = frame.get("gripper_position")
    if (
        isinstance(gripper, bool)
        or not isinstance(gripper, (int, float))
        or not math.isfinite(gripper)
    ):
        raise ConversionError(f"{location}: gripper_position must be finite")
    frame["gripper_position"] = float(gripper)
    for field in ("action", "joint_positions"):
        if not -1e-6 <= frame[field][-1] <= 1.0 + 1e-6:
            raise ConversionError(f"{location}: {field} gripper must be in [0, 1]")
    if not -1e-6 <= frame["gripper_position"] <= 1.0 + 1e-6:
        raise ConversionError(f"{location}: gripper_position must be in [0, 1]")
    return frame


def _read_episode(path: Path) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                raise ConversionError(f"{path}:{line_number}: empty JSONL row")
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ConversionError(
                    f"{path}:{line_number}: invalid JSON: {exc}"
                ) from exc
            frames.append(
                _validate_frame(
                    value,
                    location=f"{path}:{line_number}",
                    expected_sequence=len(frames),
                )
            )
    if not frames:
        raise ConversionError(f"episode is empty: {path}")
    timestamps = [frame["observation_time_ns"] for frame in frames]
    for index, (previous, current) in enumerate(pairwise(timestamps), start=2):
        if current <= previous:
            raise ConversionError(
                f"{path}:{index}: observation_time_ns must be strictly increasing"
            )
    return frames


def _nearest_indices(timestamps: list[int], fps: int) -> tuple[list[int], float]:
    start = timestamps[0]
    duration_ns = timestamps[-1] - start
    target_count = math.floor(duration_ns * fps / 1_000_000_000) + 1
    indices: list[int] = []
    max_error_ns = 0.0
    for frame_index in range(target_count):
        target = start + frame_index * 1_000_000_000 / fps
        right = bisect.bisect_left(timestamps, target)
        if right == 0:
            selected = 0
        elif right == len(timestamps):
            selected = len(timestamps) - 1
        else:
            left = right - 1
            selected = (
                left
                if target - timestamps[left] <= timestamps[right] - target
                else right
            )
        indices.append(selected)
        max_error_ns = max(max_error_ns, abs(timestamps[selected] - target))
    return indices, max_error_ns / 1_000_000


def prepare_episode(path: Path, *, fps: int) -> PreparedEpisode:
    if fps <= 0:
        raise ValueError("fps must be positive")
    raw = _read_episode(path)
    timestamps = [frame["observation_time_ns"] for frame in raw]
    selected, max_match_ms = _nearest_indices(timestamps, fps)
    intervals = [current - previous for previous, current in pairwise(timestamps)]
    duration_s = (timestamps[-1] - timestamps[0]) / 1_000_000_000
    actual_hz = (len(raw) - 1) / duration_s if duration_s > 0 and len(raw) > 1 else 0.0
    average_ms = sum(intervals) / len(intervals) / 1_000_000 if intervals else 0.0
    max_ms = max(intervals) / 1_000_000 if intervals else 0.0
    quality = EpisodeQuality(
        source=str(path),
        raw_samples=len(raw),
        converted_frames=len(selected),
        duration_s=duration_s,
        actual_sample_hz=actual_hz,
        average_interval_ms=average_ms,
        max_interval_ms=max_ms,
        missing_sequences=0,
        duplicate_sequences=0,
        dimension_errors=0,
        non_finite_errors=0,
        max_time_match_error_ms=max_match_ms,
    )
    return PreparedEpisode(path, tuple(raw[index] for index in selected), quality)


def _features(
    joint_names: list[str], *, include_velocity: bool, include_ee_pose: bool
) -> dict[str, Any]:
    features: dict[str, Any] = {
        "observation.state": {
            "dtype": "float32",
            "shape": (7,),
            "names": joint_names,
        },
        "action": {
            "dtype": "float32",
            "shape": (7,),
            "names": joint_names,
        },
    }
    if include_velocity:
        features["observation.velocity"] = {
            "dtype": "float32",
            "shape": (7,),
            "names": [f"{name}.velocity" for name in joint_names],
        }
    if include_ee_pose:
        features["observation.ee_pose"] = {
            "dtype": "float32",
            "shape": (7,),
            "names": ["x", "y", "z", "qx", "qy", "qz", "qw"],
        }
    return features


def _default_dataset_factory(**kwargs: Any) -> DatasetProtocol:
    try:
        from lerobot.datasets.lerobot_dataset import LeRobotDataset
    except ImportError as exc:
        raise ConversionError(
            "LeRobot dataset dependencies are not installed; run "
            "`uv sync --extra dataset` in lerobot_recorder"
        ) from exc
    return LeRobotDataset.create(**kwargs)


def convert_session(
    session: str | Path,
    output: str | Path,
    *,
    repo_id: str,
    fps: int = 30,
    include_velocity: bool = True,
    include_ee_pose: bool = True,
    dataset_factory: Any = _default_dataset_factory,
) -> ConversionReport:
    """Validate one raw session and write one local LeRobot Dataset v3."""

    session_path = Path(session).resolve()
    output_path = Path(output).resolve()
    if fps <= 0:
        raise ValueError("fps must be positive")
    if output_path.exists():
        raise ConversionError(f"output already exists: {output_path}")
    manifest = _read_manifest(session_path)
    episodes_dir = session_path / "episodes"
    episode_paths = sorted(episodes_dir.glob("episode_*.jsonl"))
    partial_paths = sorted(episodes_dir.glob("episode_*.jsonl.partial"))
    if not episode_paths:
        raise ConversionError(f"no completed episodes found in {episodes_dir}")

    prepared = tuple(prepare_episode(path, fps=fps) for path in episode_paths)
    dataset = dataset_factory(
        repo_id=repo_id,
        fps=fps,
        features=_features(
            list(manifest["joint_names"]),
            include_velocity=include_velocity,
            include_ee_pose=include_ee_pose,
        ),
        root=output_path,
        robot_type=manifest["robot_type"],
        use_videos=False,
    )
    try:
        import numpy as np

        for episode in prepared:
            for raw in episode.frames:
                frame: dict[str, Any] = {
                    "observation.state": np.asarray(
                        raw["joint_positions"], dtype=np.float32
                    ),
                    "action": np.asarray(raw["action"], dtype=np.float32),
                    "task": manifest["task"],
                }
                if include_velocity:
                    frame["observation.velocity"] = np.asarray(
                        raw["joint_velocities"], dtype=np.float32
                    )
                if include_ee_pose:
                    frame["observation.ee_pose"] = np.asarray(
                        raw["ee_pos_quat"], dtype=np.float32
                    )
                dataset.add_frame(frame)
            dataset.save_episode()
        dataset.finalize()
    except Exception as exc:
        raise ConversionError(f"LeRobot dataset writer failed: {exc}") from exc

    qualities = tuple(episode.quality for episode in prepared)
    report = ConversionReport(
        source_session=str(session_path),
        output_root=str(output_path),
        repo_id=repo_id,
        target_fps=fps,
        raw_samples=sum(item.raw_samples for item in qualities),
        converted_frames=sum(item.converted_frames for item in qualities),
        kept_episodes=len(qualities),
        ignored_partial_episodes=len(partial_paths),
        failed_episodes=0,
        episodes=qualities,
    )
    report_path = output_path / "quality_report.json"
    report_path.write_text(
        json.dumps(report.as_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report
