"""Video alignment uses the common target grid and rejects incomplete streams."""

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from test_converter import FakeDataset, _session

from lerobot_converter.converter import ConversionError, convert_session


def camera_session(tmp_path):
    session = _session(tmp_path, count=6)
    path = session / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest.update(
        format_version=2,
        cameras={
            "front": {
                "clock": "time.monotonic_ns",
                "storage": "rgb8_png",
                "width": 8,
                "height": 6,
                "fps": 30,
                "max_skew_ms": 20,
            }
        },
    )
    path.write_text(json.dumps(manifest))
    folder = session / "cameras/front/episode_000000"
    folder.mkdir(parents=True)
    rows = []
    for i in range(5):
        timestamp = 1_000_000_000 + i * 30_000_000
        Image.fromarray(np.full((6, 8, 3), i * 40, dtype=np.uint8)).save(
            folder / f"{i}.png"
        )
        rows.append(
            {
                "frame_index": i,
                "timestamp_ns": timestamp,
                "file": f"{i}.png",
                "sdk_timestamp_domain": "global_time",
                "sdk_timestamp_ms": timestamp / 1e6,
                "received_time_ns": timestamp + 1_000_000,
                "frame_number": i,
                "clock_offset_ns": 0,
                "clock_uncertainty_ns": 100,
            }
        )
    index = folder / "frames.jsonl"
    index.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return session, index, rows


def test_video_features_and_timestamp_selection(tmp_path):
    session, _, _ = camera_session(tmp_path)
    captured = {}

    def factory(**kwargs):
        captured.update(kwargs)
        captured["writer"] = FakeDataset(Path(kwargs["root"]))
        return captured["writer"]

    report = convert_session(
        session,
        tmp_path / "out",
        repo_id="local/video",
        fps=25,
        dataset_factory=factory,
    )
    assert captured["use_videos"] is True
    assert captured["features"]["observation.images.front"]["dtype"] == "video"
    # Robot target times 0,40,80ms match camera times 0,30,90ms.
    assert [
        int(row["observation.images.front"][0, 0, 0])
        for row in captured["writer"].episodes[0]
    ] == [0, 40, 120]
    assert report.episodes[0].cameras["front"]["max_time_match_error_ms"] == 10


@pytest.mark.parametrize(
    "problem",
    [
        "missing",
        "backwards",
        "hardware",
        "path",
        "bridge",
        "skew",
        "corrupt",
        "counter",
        "clock_step",
    ],
)
def test_camera_corruption_rejected_before_writer_creation(tmp_path, problem):
    session, index, rows = camera_session(tmp_path)
    options = {}
    if problem == "missing":
        (index.parent / "1.png").unlink()
    elif problem == "backwards":
        rows[1]["timestamp_ns"] = rows[0]["timestamp_ns"]
    elif problem == "hardware":
        rows[1]["sdk_timestamp_domain"] = "hardware_clock"
    elif problem == "path":
        rows[1]["file"] = "../outside.png"
    elif problem == "bridge":
        rows[1]["clock_offset_ns"] = 100
    elif problem == "counter":
        rows[1]["frame_number"] = rows[0]["frame_number"]
    elif problem == "clock_step":
        rows[1]["clock_offset_ns"] = 6_000_000
        rows[1]["sdk_timestamp_ms"] -= 6
    elif problem == "skew":
        options["max_camera_skew_ms"] = 1
    else:
        (index.parent / "1.png").write_bytes(b"not png")
    index.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def factory(**_kwargs):
        raise AssertionError("writer must not be created before camera validation")

    with pytest.raises(ConversionError):
        convert_session(
            session,
            tmp_path / "out",
            repo_id="local/bad",
            fps=25,
            dataset_factory=factory,
            **options,
        )
    assert not (tmp_path / "out").exists()


def test_depth_uses_declared_scale_and_lossless_metric_image_feature(tmp_path):
    session, index, rows = camera_session(tmp_path)
    manifest_path = session / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["cameras"]["front"].update(
        kind="depth", storage="z16_png", depth_units_m=0.00025
    )
    manifest_path.write_text(json.dumps(manifest))
    for i, row in enumerate(rows):
        Image.fromarray(np.full((6, 8), 4000 + i * 40, dtype=np.uint16)).save(
            index.parent / row["file"]
        )
        row["frame_number"] = i + (1 if i >= 2 else 0)
    index.write_text("".join(json.dumps(row) + "\n" for row in rows))
    captured = {}

    def factory(**kwargs):
        captured.update(kwargs)
        captured["writer"] = FakeDataset(Path(kwargs["root"]))
        return captured["writer"]

    report = convert_session(
        session,
        tmp_path / "depth",
        repo_id="local/depth",
        fps=25,
        dataset_factory=factory,
    )
    feature = captured["features"]["observation.images.front"]
    assert feature["dtype"] == "image"
    assert feature["info"] == {"is_depth_map": True, "depth_unit": "m"}
    images = [row["observation.images.front"] for row in captured["writer"].episodes[0]]
    assert all(
        image.shape == (6, 8, 1) and image.dtype == np.float32 for image in images
    )
    np.testing.assert_allclose([image[0, 0, 0] for image in images], [1, 1.01, 1.03])
    assert report.episodes[0].cameras["front"]["sdk_missing_frames"] == 1


@pytest.mark.parametrize("scale", [0, -1, float("nan"), True])
def test_invalid_depth_scale_rejected_before_creating_output(tmp_path, scale):
    session, _, _ = camera_session(tmp_path)
    path = session / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["cameras"]["front"].update(
        kind="depth", storage="z16_png", depth_units_m=scale
    )
    path.write_text(json.dumps(manifest))
    with pytest.raises(ConversionError, match="depth_units_m"):
        convert_session(session, tmp_path / "out", repo_id="local/invalid")
    assert not (tmp_path / "out").exists()
