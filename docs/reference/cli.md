# CLI 参考

```bash
lerobot-converter [--config FILE] SESSION OUTPUT [OPTIONS]
```

| 参数 | 默认值 / 用途 |
| --- | --- |
| `SESSION` | 原始 session 目录（必需） |
| `OUTPUT` | 新的 LeRobot 数据集目录（必需，必须不存在） |
| `--repo-id ID` | 默认 `local/<session 目录名>` |
| `--fps N` | `conversion.fps`，默认 30 |
| `--without-velocity` | 不写 `observation.velocity` |
| `--without-ee-pose` | 不写 `observation.ee_pose` |
| `--config FILE` | TOML 默认值文件 |

## CR7 适配入口

顶层 controller 使用 `tools/convert_cr7.py`，参数相同并额外校验 CR7
manifest 格式：

```bash
lerobot-converter/.venv/bin/python tools/convert_cr7.py \
  data/raw/session_20261008_133655 data/lerobot/session_20261008_133655 \
  --repo-id local/cr7_gello_demo --fps 30
```

## 退出码

成功 0；校验、IO 或写入失败 1。目标目录已存在时直接失败，不复用或覆盖。
