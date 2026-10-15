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

chunk/file 数量由 LeRobot 决定，不能假定始终只有一个文件。`meta/info.json` 的 `codebase_version` 为 `v3.0`，fps 为目标 FPS。raw v1 关闭视频；v2 的 RGB 写入 `videos/<feature>/.../*.mp4`，深度无损嵌入 Parquet。

| feature | 来源 | shape / dtype |
| --- | --- | --- |
| `observation.state` | `joint_positions` | `float32[7]` |
| `observation.images.<name>` | v2 RGB | video，读回 `float32[3,H,W]`，0..1 |
| `observation.images.<name>_depth` | v2 Z16 × depth_units_m | image，float32，米制存储，读回 `[1,H,W]` |
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

## 相机质量与深度读取

`episodes[*].cameras[流名]` 包含 raw_frames、converted_frames、unique_frames、repeated_frames、sdk_missing_frames、max_time_match_error_ms、mean_time_match_error_ms、max_allowed_skew_ms。误差描述选中帧到目标时刻的距离，不包含曝光或机器人反馈链路的物理延迟。

深度 feature 带 `info.is_depth_map=true` 和 `info.depth_unit="m"`，float32 单通道 TIFF 无损嵌入 Parquet，不经过 RGB 的有损编码或 12 位深度量化。Z16→米制只有浮点舍入，0 仍为无效值。LeRobotDataset 读取时应显式指定 `depth_output_unit="m"`；锁定版本默认读取单位是 mm。空间坐标仍为原生深度视角。
