# 配置参考

默认文件：[config/default.toml](../../config/default.toml)。显式命令行参数优先。

```toml
[conversion]
repo_id = ""
fps = 30
without_velocity = false
without_ee_pose = false
```

- `repo_id` 为空时使用 `local/<session 目录名>`。
- `fps` 是数据集目标频率，不是 raw 控制频率；重采样发生在转换阶段。
- 两个 `without_*` 控制是否写出可选特征；默认保留。

未知表或字段会报错；`fps` 必须是正整数。

```bash
lerobot-converter --config config/experiment.toml \
  data/raw/session_... data/lerobot/experiment
```
