"""Verify native depth, regular camera timeline and invalid raw protection."""

import json

import numpy as np
import pytest
from lerobot_converter.converter import ConversionError, convert_session
from PIL import Image
from test_converter import FakeDataset, _session


def rgbd(tmp_path):
    root = _session(tmp_path)
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["format_version"] = 2
    manifest["cameras"] = {}
    for name, kind in [("front", "color"), ("front_depth", "depth")]:
        metadata = {"kind": kind, "width": 2, "height": 2, "max_skew_ms": 10}
        if kind == "depth":
            metadata["depth_units_m"] = 0.001
        manifest["cameras"][name] = metadata
        folder = root / "cameras" / name / "episode_000000"
        folder.mkdir(parents=True)
        rows = []
        for i in range(4):
            pixels = (
                np.full((2, 2, 3), i * 20, np.uint8)
                if kind == "color"
                else np.array([[0, 65535], [1000, 2000]], np.uint16)
            )
            Image.fromarray(pixels).save(folder / f"{i}.png")
            rows.append(
                {
                    "timestamp_ns": 1_000_000_000 + round(i * 1e9 / 30),
                    "file": f"{i}.png",
                }
            )
        (folder / "frames.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
    (root / "manifest.json").write_text(json.dumps(manifest))
    return root


def test_rgbd_matches_regular_timeline_and_preserves_depth(tmp_path):
    root = rgbd(tmp_path)
    dataset = None

    def factory(**kwargs):
        nonlocal dataset
        dataset = FakeDataset(kwargs["root"])
        assert kwargs["use_videos"]
        return dataset

    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    report = convert_session(
        root, tmp_path / "dataset", repo_id="local/rgbd", dataset_factory=factory
    )
    assert dataset is not None
    for i, frame in enumerate(dataset.episodes[0]):
        assert int(frame["observation.images.front"][0, 0, 0]) == i * 20
        np.testing.assert_allclose(
            frame["observation.images.front_depth"][..., 0],
            [[0, 65.535], [1, 2]],
            rtol=1e-6,
        )
    assert report.episodes[0].cameras["front"]["max_time_match_error_ms"] == 0
    assert before == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("failure", ["path", "clock", "missing", "scale"])
def test_invalid_camera_inputs_fail_before_dataset_creation(tmp_path, failure):
    root = rgbd(tmp_path)
    index = root / "cameras/front/episode_000000/frames.jsonl"
    rows = [json.loads(row) for row in index.read_text().splitlines()]
    if failure == "path":
        rows[0]["file"] = "../../../../outside.png"
    elif failure == "clock":
        rows[0]["timestamp_ns"] -= 1_000_000_000
    elif failure == "missing":
        rows[0]["file"] = "missing.png"
    else:
        manifest = json.loads((root / "manifest.json").read_text())
        manifest["cameras"]["front_depth"]["depth_units_m"] = -1
        (root / "manifest.json").write_text(json.dumps(manifest))
    index.write_text("\n".join(json.dumps(row) for row in rows))
    with pytest.raises(ConversionError):
        convert_session(
            root,
            tmp_path / "dataset",
            repo_id="local/invalid",
            dataset_factory=lambda **kwargs: pytest.fail("created invalid dataset"),
        )
    assert not (tmp_path / "dataset").exists()
