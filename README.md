# lerobot_recorder

将 `piper_x_follow_record.py` 产生的不可变 raw session 离线转换为 LeRobot Dataset v3。转换器使用 `observation_time_ns` 建立目标时间轴并选择最近的原始样本，不使用固定步长抽帧。

## 环境

```bash
cd ~/projects/robot/lerobot_recorder
uv sync --extra dataset
```

Linux 下锁文件使用 PyTorch CPU wheel；转换纯关节数据不需要 CUDA。

### Python 依赖与系统视频库

`.venv` 只管理 Python 包。`uv sync --extra dataset` 会安装 LeRobot、PyTorch、TorchCodec 和 PyAV，但 TorchCodec 自带的 `libtorchcodec_core*.so` 仍需要 Ubuntu 系统提供 FFmpeg 共享库，例如 `libavutil.so`、`libavcodec.so` 和 `libavformat.so`。即使转换命令正在 `lerobot_recorder/.venv` 中运行，Linux 动态链接器仍会从系统库路径加载这些原生依赖。

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
lerobot_recorder/.venv/bin/python -c \
  "from torchcodec.decoders import VideoDecoder; print('TorchCodec 加载正常')"

lerobot_recorder/.venv/bin/python -c \
  "from lerobot.utils.import_utils import get_safe_default_video_backend; print(get_safe_default_video_backend())"
```

第二条命令应输出 `torchcodec`。如果仍输出很长的 `Could not load libtorchcodec` 警告，应检查报错中缺失的 `libav*.so` 和 Torch/TorchCodec 版本兼容性，不要只重复创建虚拟环境。

当数据集只有关节数据且 `use_videos=False` 时，TorchCodec 加载失败后 LeRobot 会回退到 PyAV，如果日志最后显示 `failed_episodes: 0` 和 `LeRobot Dataset 已生成`，则转换并未失败。但项目后续要加入视频，因此应提前安装并验证系统 FFmpeg，不应长期依赖自动回退。

## 转换

```bash
uv run --extra dataset lerobot-recorder \
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

## 测试

```bash
uv run --group dev pytest
uv run --group dev ruff check .
```
