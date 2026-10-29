from __future__ import annotations

from pathlib import Path

import pytest
from lerobot_converter import _parser
from lerobot_converter.configuration import load_config


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "default.toml"
    path.write_text(text)
    return path


def test_defaults() -> None:
    config = load_config()
    assert config.conversion.fps == 30
    assert config.conversion.repo_id == ""
    assert config.conversion.without_velocity is False
    args = _parser(config).parse_args(["raw", "out"])
    assert args.fps == 30
    assert args.repo_id is None


def test_overrides(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
[conversion]
repo_id = "local/demo"
fps = 15
without_velocity = true
""",
    )
    args = _parser(load_config(path)).parse_args(["raw", "out"])
    assert args.fps == 15
    assert args.repo_id == "local/demo"
    assert args.without_velocity is True
    assert args.without_ee_pose is False


def test_unknown_and_invalid(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown configuration sections"):
        load_config(write(tmp_path, "[nope]\nx = 1\n"))
    with pytest.raises(ValueError, match="unknown conversion options"):
        load_config(write(tmp_path, "[conversion]\nnope = 1\n"))
    with pytest.raises(TypeError, match="fps"):
        load_config(write(tmp_path, "[conversion]\nfps = 0\n"))
