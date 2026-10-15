# CLI 参考

```bash
uv run --extra dataset lerobot-converter SESSION OUTPUT [OPTIONS]
```

命令在 converter 根目录执行。SESSION 是 raw session，OUTPUT 是尚不存在的目标目录；相对路径以当前工作目录为基准。帮助不会创建数据集。

## 参数

| 参数 | 默认值 / 行为 |
| --- | --- |
| `SESSION` | 必填；包含 manifest 和 episodes 的目录 |
| `OUTPUT` | 必填；拒绝覆盖已存在目录 |
| `--repo-id ID` | `local/<session目录名>`，本地元数据 ID，不触发上传 |
| `--fps N` | `30`，正整数目标 FPS |
| `--without-velocity` | 不写 `observation.velocity` |
| `--without-ee-pose` | 不写 `observation.ee_pose` |

最小示例：

```bash
uv run --extra dataset lerobot-converter ../data/raw/SESSION ../data/lerobot/DATASET
```

替换占位目录即可。只有需要覆盖默认值时才添加选项，例如 `--fps 25`。关闭输出 feature 后 raw 仍必须包含 velocity 和末端字段，详见[数据格式](raw-format.md)。

## 结果与退出码

成功返回 0，stdout 输出质量报告 JSON，并在输出根目录写 `quality_report.json`。已处理的转换、路径和数值错误返回 1 并向 stderr 输出原因；argparse 语法错误返回 2。依赖可能输出额外日志，需要可靠读取报告时以报告文件为准。

校验失败不会创建 writer；写入阶段失败可能留下不完整输出，程序不会自动删除或覆盖它。保留 raw，排查后使用新的输出路径。`.partial` 只统计，不参与写入。

## controller 入口

在 controller 根目录使用 `uv run agilex-controller convert SESSION OUTPUT`，或采集后自动转换。controller 使用 converter 自己的解释器调用同一 CLI，并传入应用配置值。本库不读取 controller TOML，也不管理硬件关闭流程。
