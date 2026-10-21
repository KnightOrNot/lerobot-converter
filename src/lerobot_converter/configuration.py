"""Validated conversion defaults from ``config/default.toml``."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any


def _default_config_path() -> Path | None:
    package = Path(__file__).resolve().parent
    for candidate in (
        package.parents[1] / "config/default.toml",
        package / "default.toml",
    ):
        if candidate.exists():
            return candidate
    return None


DEFAULT_CONFIG = _default_config_path()


@dataclass(frozen=True)
class ConversionConfig:
    repo_id: str = ""
    fps: int = 30
    without_velocity: bool = False
    without_ee_pose: bool = False


@dataclass(frozen=True)
class Config:
    path: Path | None
    conversion: ConversionConfig = ConversionConfig()

    def validate(self) -> None:
        conversion = self.conversion
        if not isinstance(conversion.repo_id, str):
            raise TypeError("conversion.repo_id must be a string")
        if isinstance(conversion.fps, bool) or not isinstance(conversion.fps, int):
            raise TypeError("conversion.fps must be a positive integer")
        if conversion.fps <= 0:
            raise TypeError("conversion.fps must be a positive integer")
        if not isinstance(conversion.without_velocity, bool):
            raise TypeError("conversion.without_velocity must be a boolean")
        if not isinstance(conversion.without_ee_pose, bool):
            raise TypeError("conversion.without_ee_pose must be a boolean")


def load_config(path: str | Path | None = None) -> Config:
    selected = Path(path).resolve() if path is not None else DEFAULT_CONFIG
    if selected is None:
        data: dict[str, Any] = {}
    else:
        with Path(selected).open("rb") as stream:
            data = tomllib.load(stream)
    unknown = data.keys() - {"conversion"}
    if unknown:
        raise ValueError(f"unknown configuration sections: {sorted(unknown)}")
    values = data.get("conversion", {})
    if not isinstance(values, dict):
        raise TypeError("conversion must be a TOML table")
    unknown = values.keys() - {field.name for field in fields(ConversionConfig)}
    if unknown:
        raise ValueError(f"unknown conversion options: {sorted(unknown)}")
    try:
        conversion = ConversionConfig(**values)
    except TypeError as exc:
        raise ValueError(f"invalid conversion options: {exc}") from exc
    result = Config(
        path=Path(selected) if selected is not None else None,
        conversion=conversion,
    )
    result.validate()
    return result
