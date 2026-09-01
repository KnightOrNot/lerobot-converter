# lerobot_converter 开发与调试手册

本文档记录转换器的数据约定、依赖诊断、转换参数、质量校验和测试方法。项目简介、架构和首次安装流程请先阅读[项目 README](../README.md)。以下命令默认在 `lerobot_converter/` 目录执行。

将 `piper_x_follow_record.py` 产生的不可变 raw session 离线转换为 LeRobot Dataset v3。转换器使用 `observation_time_ns` 建立目标时间轴并选择最近的原始样本，不使用固定步长抽帧。

## （1）开发环境

```bash
cd /path/to/robot/lerobot_converter
uv sync --frozen --extra dataset
```

Linux 下锁文件使用 PyTorch CPU wheel；转换纯关节数据不需要 CUDA。

### 1. Python 依赖与系统视频库

`.venv` 只管理 Python 包。`uv sync --extra dataset` 会安装 LeRobot、PyTorch、TorchCodec 和 PyAV，但 TorchCodec 自带的 `libtorchcodec_core*.so` 仍需要 Ubuntu 系统提供 FFmpeg 共享库，例如 `libavutil.so`、`libavcodec.so` 和 `libavformat.so`。即使转换命令正在 `lerobot_converter/.venv` 中运行，Linux 动态链接器仍会从系统库路径加载这些原生依赖。

Ubuntu 22.04 需要额外安装系统 FFmpeg：

```bash
sudo apt update
sudo apt install -y ffmpeg
sudo ldconfig
```

不要使用 `pip install ffmpeg` 或 `uv add ffmpeg` 代替上述命令，因为同名 Python 包通常不提供 TorchCodec 需要的系统 `.so` 共享库。安装后先检查 FFmpeg：

```bash
ffmpeg -version
```

然后在项目根目录验证 TorchCodec 和 LeRobot 的默认视频后端：

```bash
.venv/bin/python -c \
  "from torchcodec.decoders import VideoDecoder; print('TorchCodec 加载正常')"

.venv/bin/python -c \
  "from lerobot.utils.import_utils import get_safe_default_video_backend; print(get_safe_default_video_backend())"
```

第二条命令应输出 `torchcodec`。如果仍输出很长的 `Could not load libtorchcodec` 警告，应检查报错中缺失的 `libav*.so` 和 Torch/TorchCodec 版本兼容性，不要只重复创建虚拟环境。

当数据集只有关节数据且 `use_videos=False` 时，TorchCodec 加载失败后 LeRobot 会回退到 PyAV，如果日志最后显示 `failed_episodes: 0` 和 `LeRobot Dataset 已生成`，则转换并未失败。但项目后续要加入视频，因此应提前安装并验证系统 FFmpeg，不应长期依赖自动回退。

## （2）模块结构与调用链

```text
lerobot-converter CLI
  → lerobot_converter.__init__.main()
  → converter.convert_session()
      ├── _read_manifest()
      ├── prepare_episode()
      │   ├── _read_episode()
      │   ├── _validate_frame()
      │   └── _nearest_indices()
      ├── LeRobotDataset.create()
      ├── add_frame() / save_episode() / finalize()
      └── quality_report.json
```

`__init__.py` 只负责 CLI 参数、错误出口和 JSON 报告输出；所有可测试的转换逻辑位于 `converter.py`。`DatasetProtocol` 用于在单元测试中注入轻量 fake dataset，避免测试依赖真实磁盘格式和完整 LeRobot 写入过程。

## （3）Raw 数据约定

输入 session 必须采用以下结构：

```text
session_YYYYMMDD_HHMMSS/
├── manifest.json
└── episodes/
    ├── episode_000000.jsonl
    ├── episode_000001.jsonl
    └── episode_000002.jsonl.partial
```

manifest 必须声明 `piper_x_gello_raw`、格式版本 1、单调时钟、PiPER-X、弧度/米单位、`xyzw` 四元数顺序、七个关节名称、正有限 `control_hz` 和 `[0.0, 1.0]` 夹爪范围。转换器不会猜测或自动修复不符合约定的 manifest。

每行 JSONL 必须包含非负整数时间字段和连续的 `sequence`，并包含以下有限数值向量：

| 字段                 | 维度  | 含义                        |
| ------------------ | --- | ------------------------- |
| `action`           | 7   | 实际下发的 J1～J6 目标和夹爪目标       |
| `joint_positions`  | 7   | 机械臂反馈位置和夹爪反馈              |
| `joint_velocities` | 7   | 六轴及夹爪速度                   |
| `ee_pos_quat`      | 7   | `x, y, z, qx, qy, qz, qw` |

正式的 `.jsonl` 会参与转换；异常退出留下的 `.jsonl.partial` 只计入 `ignored_partial_episodes`，不会静默混入数据集。转换器只读 raw session，不修改、恢复或删除输入文件。

## （4）校验与重采样

`prepare_episode()` 首先逐行解析并验证 JSONL，然后要求 `observation_time_ns` 严格递增。目标帧数按 episode 的真实持续时间和 `--fps` 计算，每个目标时刻通过二分搜索选择时间最近的原始 observation。

这种方法不会使用固定步长。例如原始数据约为 50 Hz、目标为 30 FPS 时，固定每两帧抽一帧只会得到约 25 FPS；基于时间戳选择能够处理非整数频率比和控制周期抖动。当前实现允许不同目标时刻选择同一个最近原始帧，相关误差会写入 `max_time_match_error_ms`。

遇到下列情况会立即抛出 `ConversionError`，避免生成看似成功但语义错误的数据集：

- manifest 缺失、JSON 损坏或单位约定不匹配；
- session 中没有正式 episode；
- sequence 不连续；
- observation 时间戳重复或倒退；
- 七维字段缺失、维度错误或包含 NaN/Inf；
- action、joint position 或独立夹爪反馈超出 `[0, 1]`；
- 输出目录已经存在；
- LeRobot writer 创建、写帧、保存 episode 或 finalize 失败。

## （5）手工转换

```bash
uv run --extra dataset lerobot-converter \
  ../data/raw/session_20260831_115727 \
  ../data/lerobot/session_20260831_115727 \
  --repo-id local/piper_x_gello_session_20260831_115727 \
  --fps 30
```

输出目录必须尚不存在，以免覆盖已有数据集。默认包含以下 feature：

- `joint_positions` → `observation.state`
- `action` → `action`
- `joint_velocities` → `observation.velocity`
- `ee_pos_quat` → `observation.ee_pose`

可用 `--without-velocity` 或 `--without-ee-pose` 排除可选 feature。正式 `.jsonl` episode 会被转换，`.jsonl.partial` 会被统计并忽略。发现 manifest、sequence、维度、时间戳、NaN/Inf 或单位约定错误时，转换会直接失败。

LeRobot 在 `meta/` 和 `data/` 下生成 v3 元数据与 Parquet 数据；转换器另写入 `quality_report.json`，记录每个 episode 的原始/转换帧数、实际频率、最大采样间隔和最大时间匹配误差。

## （6）调试流程

### 1. 只验证 raw，不写真实 LeRobot 数据集

可以在 Python 中调用 `prepare_episode()` 检查单个 episode 的解析、时间戳和重采样结果：

```bash
uv run python -c "from pathlib import Path; from lerobot_converter.converter import prepare_episode; print(prepare_episode(Path('../data/raw/SESSION/episodes/episode_000000.jsonl'), fps=30).quality)"
```

### 2. 输出目录已存在

这是防覆盖保护，不是转换器异常。不要让转换器覆盖已有数据集；请选择新目录，或在人工确认旧目录可删除后自行处理旧输出。raw session 不应随派生数据一起删除。

### 3. LeRobot 依赖未安装

如果看到 `LeRobot dataset dependencies are not installed`，说明当前环境只安装了基础项目，执行：

```bash
uv sync --frozen --extra dataset
```

### 4. TorchCodec 警告

先分别确认 Python 包和系统动态库。`.venv` 中存在 `torchcodec` 不代表 Ubuntu 已提供 FFmpeg `.so`；根据警告中的缺失库检查 `ldconfig -p | grep libav`，并核对 Torch 与 TorchCodec 的兼容版本。纯关节转换当前设置 `use_videos=False`，但加入视频前必须消除该问题。

### 5. 自动转换没有运行

`start_data_record.sh` 只有在 session 中至少存在一个正式 `episode_*.jsonl` 时才调用转换器。只有 `.jsonl.partial`、episode 被丢弃、使用了 `--skip-conversion`、转换器可执行文件不存在，都会导致跳过或提前报错。先检查：

```bash
find ../data/raw/SESSION/episodes -maxdepth 1 -type f -print
test -x .venv/bin/lerobot-converter && echo "转换器入口正常"
```

## （7）测试与静态检查

```bash
uv run --group dev pytest
uv run --group dev ruff check .
```

测试修改转换规则时，至少覆盖成功转换、manifest 错误、sequence 错误、非有限值、时间戳错误、partial episode、可选 feature 和输出目录防覆盖。测试不应依赖真实 PiPER-X、GELLO、CAN 或串口。
