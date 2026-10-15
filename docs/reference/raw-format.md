# Raw v1 数据格式

输入来自 controller 的 raw recorder，或任何遵守相同约定的生产者。转换器仅校验和读取，不修复输入。

## Session 文件结构

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

## manifest.json

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

## episode_*.jsonl

每行必须是一个独立 JSON object，不允许空行。下面是一帧结构示例；数组中的数值仅用于说明维度：

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

## 配对与可选输出

同一行的 action 和 observation 作为一对保留。当前 controller 在发送 action 后读取 observation；转换器不补偿执行延迟。command 和 observation 时间戳都必填，但仅 observation 时间戳用于构造目标轴。

`--without-velocity`、`--without-ee-pose` 只改变输出 feature，不允许从 raw 中省略对应字段。夹爪约定指从臂命令/反馈；主手物理开闭方向由应用校准，不由 converter 推断。当前 schema 不包含图像或视频。
