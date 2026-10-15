# 输出与质量报告

## LeRobot Dataset v3

```text
OUTPUT_DATASET/
├── data/chunk-000/file-000.parquet
├── meta/
│   ├── episodes/chunk-000/file-000.parquet
│   ├── info.json
│   ├── stats.json
│   └── tasks.parquet
└── quality_report.json
```

chunk/file 数量由 LeRobot 决定，不能假定始终只有一个文件。`meta/info.json` 的 `codebase_version` 为 `v3.0`，fps 为目标 FPS。当前关闭视频写入，不生成视频 feature。

| feature | 来源 | shape / dtype |
| --- | --- | --- |
| `observation.state` | `joint_positions` | `float32[7]` |
| `action` | `action` | `float32[7]` |
| `observation.velocity` | `joint_velocities`，可关闭 | `float32[7]` |
| `observation.ee_pose` | XYZ 米与 XYZW 四元数，可关闭 | `float32[7]` |

manifest task 随每帧传给 LeRobot，映射到任务表和 `task_index`。LeRobot 自动生成 `index`、`episode_index`、`frame_index`、`timestamp`。原始 command/observation/wall 纳秒时间不作为输出 feature 保留；需要追溯时读取 raw。

## 质量报告

`quality_report.json` 是转换器附加文件，不是 LeRobot 标准元数据。成功转换后 CLI 返回相同报告内容。

| 字段 | 含义 |
| --- | --- |
| `source_session` / `output_root` / `repo_id` | 输入输出绝对路径与数据集 ID |
| `target_fps` | 目标重采样频率 |
| `raw_samples` / `converted_frames` | 正式 episode 原始样本和输出帧数总和 |
| `kept_episodes` / `ignored_partial_episodes` | 已转换正式集数 / 忽略的 partial 数 |
| `failed_episodes` | 成功报告中为 0；遇错直接失败，不是跳过坏集后的统计 |
| `episodes` | 每集质量指标列表 |

每集包含 source、样本/帧数、持续时长、实际采样频率、平均/最大采样间隔、最大目标时间匹配误差。间隔和误差用 ms；实际频率为 `(样本数 - 1) / 持续时间`，单样本时为 0。错误计数当前只会在成功校验后记录 0，不能理解为自动修复了损坏数据。

重采样可能重复选择同一行，应结合 `max_time_match_error_ms` 和 `max_interval_ms` 评估质量，而非只看输出 FPS。原始 50 Hz 的目标控制值不保证真实采样也为 50 Hz。
