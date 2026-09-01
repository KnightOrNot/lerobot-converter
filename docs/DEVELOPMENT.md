# lerobot_converter 开发与调试手册

本文档记录转换器的数据约定、依赖诊断、转换参数、质量校验和测试方法。项目简介、架构和首次安装流程请先阅读[项目 README](../README.md)。以下命令默认在 `lerobot_converter/` 目录执行。

将 `piper_x_follow_record.py` 产生的不可变 raw session 离线转换为 LeRobot Dataset v3。转换器使用 `observation_time_ns` 建立目标时间轴并选择最近的原始样本，不使用固定步长抽帧。

## （1）开发环境

```bash
cd /path/to/robot/lerobot_converter
requested_version="$(<.python-version)"
resolved_version="$(pyenv latest -k "$requested_version")"
pyenv install -s "$resolved_version"
interpreter="$(PYENV_VERSION="$resolved_version" pyenv which python)"
UV_NO_MANAGED_PYTHON=1 uv sync --frozen --extra dataset --python "$interpreter"
```

pyenv 负责安装和选择 Python，uv 负责 `.venv`、锁定依赖和命令运行；不要让 uv 创建另一套解释器。Linux 下锁文件使用 PyTorch CPU wheel；转换纯关节数据不需要 CUDA。

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

### 1. Session 文件结构

输入 session 必须采用以下结构：

```text
session_YYYYMMDD_HHMMSS/
├── manifest.json
└── episodes/
    ├── episode_000000.jsonl
    ├── episode_000001.jsonl
    └── episode_000002.jsonl.partial
```

目录名称没有强制格式，但推荐使用 `session_YYYYMMDD_HHMMSS`。`episodes/` 中至少需要一个正式的 `episode_*.jsonl`；文件按名称排序后依次转换为 LeRobot episode。`.jsonl.partial` 表示异常退出或尚未正式保存的 episode，只会计入质量报告，不参与转换。

### 2. `manifest.json`

转换器接受的最小 manifest 如下：

```json
{
  "format": "piper_x_gello_raw",
  "format_version": 1,
  "clock": "time.monotonic_ns",
  "robot_type": "piper_x",
  "control_hz": 50.0,
  "task": "pick up the object",
  "joint_units": "rad",
  "velocity_units": "rad/s",
  "position_units": "m",
  "gripper_range": [0.0, 1.0],
  "quaternion_order": "xyzw",
  "joint_names": [
    "joint_1",
    "joint_2",
    "joint_3",
    "joint_4",
    "joint_5",
    "joint_6",
    "gripper"
  ]
}
```

字段约束如下：

| 字段 | 类型 | 必须值或约束 |
| --- | --- | --- |
| `format` | string | 固定为 `piper_x_gello_raw` |
| `format_version` | integer | 固定为 `1` |
| `clock` | string | 固定为 `time.monotonic_ns` |
| `robot_type` | string | 固定为 `piper_x` |
| `control_hz` | number | 原始控制目标频率，必须为正有限数 |
| `task` | string | 非空任务描述，将写入每一帧的 `task` |
| `joint_units` | string | 固定为 `rad` |
| `velocity_units` | string | 固定为 `rad/s` |
| `position_units` | string | 固定为 `m` |
| `gripper_range` | array | 固定为 `[0.0, 1.0]`，其中 `0=全闭`、`1=全开` |
| `quaternion_order` | string | 固定为 `xyzw` |
| `joint_names` | array | 七个非空字符串，顺序对应 J1～J6 和 gripper |

记录器可以添加 `created_at`、`joint_signs`、`sample_fields` 等扩展字段；当前转换器会保留输入只读，但不会把这些扩展字段直接映射为 LeRobot feature。转换器不会猜测或自动修复不符合约定的 manifest。

### 3. `episode_*.jsonl`

每个非空行都是一个独立 JSON object。下面是一帧结构示例；数组中的数值仅用于说明维度：

```json
{"command_time_ns": 5339991845319, "observation_time_ns": 5340010854960, "wall_time_ns": 1787745153814467185, "control_period_ns": 21037629, "action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], "joint_positions": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.993], "joint_velocities": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "ee_pos_quat": [0.1, 0.0, 0.2, 0.0, 0.0, 0.0, 1.0], "gripper_position": 0.993, "sequence": 0}
```

整数与标量字段约束：

| 字段 | 类型 | 约束与语义 |
| --- | --- | --- |
| `sequence` | integer | 从 0 开始且逐帧连续，不允许缺失或重复 |
| `command_time_ns` | integer | 发送 action 时的非负单调时钟时间，ns |
| `observation_time_ns` | integer | 获取 observation 时的非负单调时钟时间，ns；episode 内必须严格递增 |
| `wall_time_ns` | integer | 对应帧的非负墙上时钟时间，ns |
| `control_period_ns` | integer | 当前控制周期，ns，必须非负 |
| `gripper_position` | number | 独立夹爪反馈，有限数且位于 `[0, 1]` |

向量字段约束：

| 字段 | 维度 | 顺序、单位和约束 |
| --- | --- | --- |
| `action` | 7 | J1～J6 为 rad，第七维 gripper 位于 `[0, 1]` |
| `joint_positions` | 7 | J1～J6 为 rad，第七维 gripper 位于 `[0, 1]` |
| `joint_velocities` | 7 | J1～J6 为 rad/s，第七维为 gripper velocity |
| `ee_pos_quat` | 7 | `x, y, z` 为 m，后四维为 `qx, qy, qz, qw` |

所有向量元素必须是有限数值，不能包含布尔值、NaN 或 Inf。转换器只读 raw session，不修改、恢复或删除输入文件。

## （4）LeRobot Dataset v3 输出约定

转换成功后生成以下目录。实际 chunk 和 file 编号由 LeRobot 根据数据量决定，不保证只有 `chunk-000/file-000.parquet`：

```text
OUTPUT_DATASET/
├── data/
│   └── chunk-000/
│       └── file-000.parquet
├── meta/
│   ├── episodes/
│   │   └── chunk-000/
│   │       └── file-000.parquet
│   ├── info.json
│   ├── stats.json
│   └── tasks.parquet
└── quality_report.json
```

LeRobot feature 映射如下：

| LeRobot feature | dtype/shape | 来源 | 是否可关闭 |
| --- | --- | --- | --- |
| `observation.state` | `float32[7]` | `joint_positions` | 否 |
| `action` | `float32[7]` | `action` | 否 |
| `observation.velocity` | `float32[7]` | `joint_velocities` | 是，使用 `--without-velocity` |
| `observation.ee_pose` | `float32[7]` | `ee_pos_quat` | 是，使用 `--without-ee-pose` |
| `task` | string input | manifest 的 `task` | 否，由 LeRobot 映射为 `task_index` |

LeRobot 自动生成 `index`、`episode_index`、`frame_index`、`timestamp` 和 `task_index`，转换器不会在 `add_frame()` 时手工提供这些字段。`meta/info.json` 应包含 `"codebase_version": "v3.0"`、目标 `fps`、feature schema、episode/frame/task 总数、数据路径模板和 `robot_type`。`data/**/*.parquet` 保存逐帧数据，`meta/episodes/**/*.parquet` 保存 episode 元数据，`meta/stats.json` 保存统计信息，`meta/tasks.parquet` 保存任务表。

`quality_report.json` 是本项目附加的非标准文件，不影响 LeRobot 加载。它记录输入输出路径、repo ID、目标 FPS、raw/转换帧数、保留和忽略的 episode 数，以及每个 episode 的实际采样率、平均/最大间隔和最大时间匹配误差。

## （5）校验与重采样

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

## （6）手工转换

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

## （7）调试流程

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

## （8）测试与静态检查

```bash
uv run --group dev pytest
uv run --group dev ruff check .
```

测试修改转换规则时，至少覆盖成功转换、manifest 错误、sequence 错误、非有限值、时间戳错误、partial episode、可选 feature 和输出目录防覆盖。测试不应依赖真实 PiPER-X、GELLO、CAN 或串口。
