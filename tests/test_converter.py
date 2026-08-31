from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from lerobot_recorder.converter import ConversionError, convert_session, prepare_episode


def _frame(sequence: int, timestamp_ns: int) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "command_time_ns": timestamp_ns - 1,
        "observation_time_ns": timestamp_ns,
        "wall_time_ns": timestamp_ns + 1,
        "control_period_ns": 20_000_000,
        "action": [0.0] * 6 + [1.0],
        "joint_positions": [0.1] * 6 + [0.5],
        "joint_velocities": [0.0] * 7,
        "ee_pos_quat": [0.0, 0.0, 0.2, 0.0, 0.0, 0.0, 1.0],
        "gripper_position": 0.5,
    }


def _session(tmp_path: Path, count: int = 6) -> Path:
    session = tmp_path / "session_20260101_000000"
    episodes = session / "episodes"
    episodes.mkdir(parents=True)
    manifest = {
        "format": "piper_x_gello_raw",
        "format_version": 1,
        "clock": "time.monotonic_ns",
        "robot_type": "piper_x",
        "control_hz": 50.0,
        "task": "pick object",
        "joint_units": "rad",
        "velocity_units": "rad/s",
        "position_units": "m",
        "gripper_range": [0.0, 1.0],
        "quaternion_order": "xyzw",
        "joint_names": [f"joint_{index}" for index in range(1, 7)] + ["gripper"],
    }
    (session / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    rows = [_frame(index, 1_000_000_000 + index * 20_000_000) for index in range(count)]
    (episodes / "episode_000000.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    return session


class FakeDataset:
    def __init__(self, root: Path) -> None:
        root.mkdir()
        self.current: list[dict[str, Any]] = []
        self.episodes: list[list[dict[str, Any]]] = []
        self.finalized = False

    def add_frame(self, frame: dict[str, Any]) -> None:
        self.current.append(frame)

    def save_episode(self) -> None:
        self.episodes.append(self.current)
        self.current = []

    def finalize(self) -> None:
        self.finalized = True


def test_prepare_episode_uses_timestamp_nearest_neighbor(tmp_path: Path) -> None:
    session = _session(tmp_path, count=6)
    prepared = prepare_episode(session / "episodes/episode_000000.jsonl", fps=25)

    assert prepared.quality.raw_samples == 6
    assert prepared.quality.converted_frames == 3
    assert [frame["sequence"] for frame in prepared.frames] == [0, 2, 4]
    assert prepared.quality.actual_sample_hz == pytest.approx(50.0)


def test_convert_maps_features_and_writes_report(tmp_path: Path) -> None:
    session = _session(tmp_path)
    fake: FakeDataset | None = None
    factory_args: dict[str, Any] = {}

    def factory(**kwargs: Any) -> FakeDataset:
        nonlocal fake
        factory_args.update(kwargs)
        fake = FakeDataset(Path(kwargs["root"]))
        return fake

    output = tmp_path / "dataset"
    report = convert_session(
        session,
        output,
        repo_id="local/test",
        fps=25,
        dataset_factory=factory,
    )

    assert fake is not None and fake.finalized
    assert len(fake.episodes) == 1
    assert set(fake.episodes[0][0]) == {
        "observation.state",
        "observation.velocity",
        "observation.ee_pose",
        "action",
        "task",
    }
    assert "timestamp" not in fake.episodes[0][0]
    assert factory_args["features"]["observation.state"]["shape"] == (7,)
    assert report.converted_frames == 3
    assert (output / "quality_report.json").is_file()


def test_rejects_sequence_gap(tmp_path: Path) -> None:
    session = _session(tmp_path, count=2)
    path = session / "episodes/episode_000000.jsonl"
    rows = [_frame(0, 1_000_000_000), _frame(2, 1_020_000_000)]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    with pytest.raises(ConversionError, match="expected sequence 1, got 2"):
        prepare_episode(path, fps=30)


def test_ignores_partial_episode(tmp_path: Path) -> None:
    session = _session(tmp_path)
    partial = session / "episodes/episode_000001.jsonl.partial"
    partial.write_text(json.dumps(_frame(0, 1_000_000_000)) + "\n", encoding="utf-8")
    fake: FakeDataset | None = None

    def factory(**kwargs: Any) -> FakeDataset:
        nonlocal fake
        fake = FakeDataset(Path(kwargs["root"]))
        return fake

    report = convert_session(
        session,
        tmp_path / "dataset",
        repo_id="local/test",
        dataset_factory=factory,
    )

    assert report.ignored_partial_episodes == 1
