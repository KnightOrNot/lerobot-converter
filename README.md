# lerobot_converter

`lerobot_converter` 是 PiPER-X/GELLO 数据链路中的离线转换项目。它读取 `gello_software` 记录的不可变 raw session，执行格式校验、按真实时间戳重采样，并生成 LeRobot Dataset v3 和质量报告。该项目不连接 GELLO、PiPER-X、串口或 CAN，也不负责实时数据记录。

## （1）项目边界

完整数据链路分为两个阶段：

```text
阶段一：实时记录
gello_software/piper_x_follow_record.py
        ↓
data/raw/session_*/manifest.json + episodes/*.jsonl
```

```
阶段二：离线转换
lerobot_converter
        ↓ 校验、重采样、字段映射
data/lerobot/session_*/ + quality_report.json
```

各组件职责如下：

| 组件                     | 职责                                                |
| ---------------------- | ------------------------------------------------- |
| `gello_software`       | 跟随控制期间记录最终 action 和机械臂 observation，生成 raw session |
| `lerobot_converter`    | 只读 raw session，转换为 LeRobot Dataset v3             |
| `start_data_record.sh` | 编排记录、安全回零和退出后的离线转换                                |

## （2）项目结构

```text
lerobot_converter/
├── README.md
├── docs/
│   └── DEVELOPMENT.md
├── pyproject.toml
├── uv.lock
├── src/lerobot_converter/
│   ├── __init__.py
│   └── converter.py
└── tests/
    └── test_converter.py
```

- `src/lerobot_converter/__init__.py`：定义 `lerobot-converter` CLI 和参数解析。
- `src/lerobot_converter/converter.py`：实现 manifest/episode 校验、时间戳重采样、LeRobot 写入和质量报告。
- `tests/test_converter.py`：验证转换规则、失败保护、字段映射和报告内容。
- `docs/DEVELOPMENT.md`：详细的数据约定、算法、调试和测试流程。

## （3）环境要求

- Ubuntu 或其他受 LeRobot 支持的 Linux 环境
- Python 3.12（由 `.python-version` 指定）
- Git & [uv](https://docs.astral.sh/uv/getting-started/installation/)
- 转换数据集需要 dataset 可选依赖
- 后续处理视频时，系统需要 FFmpeg 共享库

本项目使用独立 `.venv`，不会修改已经通过硬件验证的 `agilexrobotics` 或 `gello_software` 环境。Linux 下锁文件选择 PyTorch CPU wheel，纯关节数据转换不需要 CUDA。

## （4）快速开始

### 1. 进入项目并初始化环境

从项目仓库 clone 后进入目录：

```bash
cd lerobot_converter
uv python install 3.12
uv sync --frozen --extra dataset
```

`uv sync` 会创建 `.venv` 并安装 LeRobot、PyTorch、TorchCodec、PyAV 以及开发工具。通常无需激活虚拟环境，后续直接使用 `uv run`。

### 2. 安装系统 FFmpeg

当前转换器尚未写入视频，但为后续视频 feature 提前安装 TorchCodec 所需的系统共享库：

```bash
sudo apt update
sudo apt install -y ffmpeg
sudo ldconfig
```

不要使用 `pip install ffmpeg` 或 `uv add ffmpeg` 替代系统包，它们不能提供 TorchCodec 所需的 `libavutil.so`、`libavcodec.so` 和 `libavformat.so`。

验证环境：

```bash
ffmpeg -version
uv run python -c "from torchcodec.decoders import VideoDecoder; print('TorchCodec 加载正常')"
uv run python -c "from lerobot.utils.import_utils import get_safe_default_video_backend; print(get_safe_default_video_backend())"
```

默认视频后端应输出 `torchcodec`。更详细的动态库排查方法见[开发与调试手册](docs/DEVELOPMENT.md#1-python-依赖与系统视频库)。

### 3. 转换 raw session

以下命令假设 `lerobot_converter/`、`data/raw/` 和 `data/lerobot/` 位于同一个工作区中：

```bash
uv run --extra dataset lerobot-converter \
  ../data/raw/session_YYYYMMDD_HHMMSS \
  ../data/lerobot/session_YYYYMMDD_HHMMSS \
  --repo-id local/piper_x_gello_session_YYYYMMDD_HHMMSS \
  --fps 30
```

输入 session 必须包含合法的 `manifest.json` 和至少一个正式的 `episodes/episode_*.jsonl`。输出目录必须尚不存在，转换器不会覆盖已有数据集。

默认字段映射：

| Raw 字段             | LeRobot feature        |
| ------------------ | ---------------------- |
| `joint_positions`  | `observation.state`    |
| `action`           | `action`               |
| `joint_velocities` | `observation.velocity` |
| `ee_pos_quat`      | `observation.ee_pose`  |

不需要可选 feature 时可使用：

```bash
uv run --extra dataset lerobot-converter \
  INPUT_SESSION OUTPUT_DATASET \
  --fps 30 \
  --without-velocity \
  --without-ee-pose
```

### 4. 检查输出

成功后输出目录包含 LeRobot v3 的 `meta/`、`data/` 等内容，以及转换器额外生成的 `quality_report.json`。报告记录每个 episode 的原始样本数、转换帧数、实际采样率、最大采样间隔和最大时间匹配误差。

```bash
python -m json.tool ../data/lerobot/session_YYYYMMDD_HHMMSS/quality_report.json
```

## （5）与数据记录脚本配合

工作区根目录的 `start_data_record.sh` 默认在记录结束、安全回零并关闭 CAN/ZMQ 后调用：

```text
lerobot_converter/.venv/bin/lerobot-converter
```

自动转换的目标 FPS 由 `--dataset-fps` 控制：

```bash
./start_data_record.sh --task "pick up the object" --dataset-fps 30
```

只保留 raw session、暂不转换时使用：

```bash
./start_data_record.sh --task "pick up the object" --skip-conversion
```

## （6）开发检查

```bash
uv run --group dev pytest
uv run --group dev ruff check .
```

转换规则、重采样算法、raw 格式要求、常见失败和调试流程见[开发与调试手册](docs/DEVELOPMENT.md)。
