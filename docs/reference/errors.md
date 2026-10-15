# 故障排查

| 现象 | 检查与处理 |
| --- | --- |
| `manifest not found` / 字段不匹配 | 输入必须指向 session 根目录，核对 [Raw v1](raw-format.md) |
| 没有 completed episode | 仅有 partial 不会转换；controller 中按 S 保存正式集 |
| sequence、维度、NaN/Inf 或时间戳错误 | 按报错文件/行排查采集端；不要删行或改 raw 来掩盖损坏 |
| `output already exists` | 选择新的输出路径；转换器拒绝覆盖旧数据 |
| dataset 依赖缺失 | `uv sync --frozen --extra dataset`，运行时保留 `--extra dataset` |
| TorchCodec 无法加载 | 检查系统 FFmpeg 的 `libav*.so` 与锁定 Torch/TorchCodec，不只重装 Python 包 |
| writer 失败或磁盘写入错误 | 检查空间、权限和依赖，可能留下不完整输出；排查后写新目录 |
| 自动转换没有运行 | 检查正式 episode、controller 的 `--skip-conversion`、converter 环境以及退出/清理是否成功 |

## 只验证单个 episode

```bash
uv run python -c "from pathlib import Path; from lerobot_converter.converter import prepare_episode; print(prepare_episode(Path('../data/raw/SESSION/episodes/episode_000000.jsonl'), fps=30).quality)"
```

这只校验 episode 行、sequence、维度、时间戳并重采样，不校验 session manifest，也不写 LeRobot。完整转换才覆盖 manifest 与真实 writer。

## 系统库与失败输出

按[安装指南](../installation.md)安装系统 FFmpeg；`ldconfig -p` 可检查动态库。纯状态转换设置 `use_videos=False`，LeRobot 的视频后端回退警告不一定表示状态转换失败，应看退出码、报告与最终数据集。后端加载成功也不表示转换器支持视频输入。

失败可能发生在 writer 创建、写帧、保存、finalize 或报告落盘阶段。不要把已有输出目录或缺少成功报告的数据集直接当作成功产物；保留原始 session，诊断后重新生成新目录。

问题报告附 CLI、提交、Python 与锁定依赖、完整错误和脱敏 raw 示例，说明使用 fake writer 还是实际 LeRobot。原始采集数据不应直接提交到 Git。
