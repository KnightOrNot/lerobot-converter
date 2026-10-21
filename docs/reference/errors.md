# 故障排查

## 缺少 LeRobot 依赖

`ModuleNotFoundError: lerobot` 表示没有安装 `dataset` extra，或使用了错误的
Python 环境。执行 `uv sync --project lerobot-converter --extra dataset --python 3.12`；
不要把依赖装进控制 SDK 环境。

## 输出目录已存在

转换要求目标目录尚不存在。审阅并移走旧输出，或选择新目录。不要把输出指向
raw 输入目录。

## manifest 或 episode 校验失败

检查 `format`、`format_version`、`robot_type`、`control_hz`、七维关节名、
时间戳单调性和有限数值。错误信息会指出文件与行；raw 不应手工修改。

## 目标目录里有 partial

转换器忽略 `.jsonl.partial`。没有正式 episode 时不会产生数据集；先按 S
保存。不要把 partial 改名冒充完整集。

## FFmpeg / TorchCodec 错误

属于转换环境问题：

```bash
ffmpeg -version
lerobot-converter/.venv/bin/python -c \
  "from torchcodec.decoders import VideoDecoder"
```

网络安装依赖失败时先完成环境同步，再重试转换。
