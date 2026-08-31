# lerobot_recorder

将 `piper_x_follow_record.py` 产生的不可变 raw session 离线转换为 LeRobot Dataset v3。转换器使用 `observation_time_ns` 建立目标时间轴并选择最近的原始样本，不使用固定步长抽帧。

## 环境

```bash
cd ~/projects/robot/lerobot_recorder
uv sync --extra dataset
```

Linux 下锁文件使用 PyTorch CPU wheel；转换纯关节数据不需要 CUDA。

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
