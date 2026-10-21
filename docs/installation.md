# 安装与环境

## 要求

- Python **3.12**；转换依赖与实时控制 SDK 环境完全分开。
- 系统 FFmpeg（图像/视频编码需要）。
- 转换数据集时安装 `dataset` extra：

```bash
uv sync --project lerobot-converter --extra dataset --python 3.12
uv run --project lerobot-converter --extra dataset python -c \
  "from lerobot.datasets.lerobot_dataset import LeRobotDataset"
```

## 验证

```bash
uv run --project lerobot-converter --with pytest --with ruff pytest -q
ffmpeg -version
```

离线测试使用合成 raw，不访问硬件。

## 在 controller 中使用

顶层 `scripts/start_data_record.sh` 调用
`lerobot-converter/.venv/bin/python tools/convert_cr7.py`；
转换器项目自身的 `.venv` 必须存在，格式和字段由 CR7 适配器校验。
不要把转换依赖安装进 `xcore-sdk-python/.venv`。
