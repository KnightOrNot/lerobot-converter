# lerobot-converter

将 PiPER-X/GELLO 的不可变 raw session 离线转换为 LeRobot Dataset v3。转换器负责格式校验、基于 observation 时间戳的重采样、数据集写入和质量报告，不连接硬件、不录制数据。

推荐 Python 3.12，使用独立环境。controller/GELLO/SDK 使用 Python 3.11，两组解释器通过文件和子进程协作。支持七维状态的 raw v1，以及 RGB/原始深度的 raw v2；多路图像分别按同一目标时间轴匹配。

## 职责与目录

```text
src/lerobot_converter/    CLI、raw 校验、重采样与 LeRobot writer
tests/                   临时 raw 与 fake writer 回归
docs/                    架构、安装、数据约定、CLI 与排障
```

## 安装

准备 Python 3.12、Git、uv；在本仓库根目录执行：

```bash
uv sync --frozen --extra dataset
uv run --extra dataset lerobot-converter --help
```

`dataset` 安装锁定的 LeRobot 0.6.1 及 PyTorch 等依赖；Linux 使用 CPU wheel，不需要 CUDA。FFmpeg 动态库与 pyenv 流程见[安装指南](docs/installation.md)。

## 转换与检查

```bash
uv run --extra dataset lerobot-converter INPUT_SESSION OUTPUT_DATASET
```

将两个路径替换为实际目录。默认输出 30 FPS，repo ID 为 `local/<session目录名>`；无需显式重复默认参数。输入必须有合法 `manifest.json` 和至少一个已保存的 `episodes/episode_*.jsonl`。`.jsonl.partial` 仅统计，不转换；输出目录必须尚不存在。

转换成功生成 LeRobot 的 `data/`、`meta/`、可选 RGB `videos/` 和附加 `quality_report.json`，CLI 同时输出报告 JSON。raw 保持原样。报告中的实际采样率、最大间隔和时间匹配误差用于判断采集质量。

## 与 controller 配合

在 controller 根目录运行：

```bash
./scripts/start_camera_record.sh
```

上述相机入口默认显示 RGB 预览，录制 RGB、深度与关节；纯关节数采沿用 `./scripts/start_data_record.sh`。按 R 开始、S 保存正式 episode。正常退出且清理成功后，controller 使用 converter 自己的解释器执行转换；`--skip-conversion` 只保留 raw。已有 session 可在 controller 中单独转换：

```bash
uv run agilex-controller convert data/raw/SESSION data/lerobot/DATASET
```

采集频率、输出 FPS 和目标路径由 controller 配置管理；converter 不读取 controller TOML。其他项目只要实现相同 [raw v1/v2 约定](docs/reference/raw-format.md)，也可独立调用本 CLI 或 Python API。

## RGB-D 与单位

raw v2 的每路图像必须有合法 `cameras/<name>/<episode>/frames.jsonl` 与无损 PNG。转换前校验索引、原始 SDK 时钟映射、图像内容和时间顺序，再按目标时间匹配；默认容差来自 manifest，可用 `--max-camera-skew-ms` 覆盖。超限拒绝转换。

RGB 作为 video 特征编码 MP4；Z16 深度乘以 manifest 中的 `depth_units_m`，以米制 float32 单通道 image 无损存储，不做深度视频量化。读取时显式 `LeRobotDataset(..., depth_output_unit="m")`，当前版本默认返回 mm。0 保持无效值；原生深度未投影到 RGB 像素。软件时间匹配不代表硬件曝光同步精度。

## 开发与文档

```bash
uv run --frozen --extra dataset pytest
uv run --frozen --extra dataset ruff check --isolated .
uv build
```

单元测试使用 fake writer，不需要设备，也不验证真实 LeRobot 文件可读性；真实 writer 的转换与读回在 controller 集成测试中验证。

- [架构与重采样](docs/index.md)
- [安装指南](docs/installation.md)
- [CLI 参考](docs/reference/cli.md)
- [Raw v1/v2 数据格式](docs/reference/raw-format.md)
- [输出与质量报告](docs/reference/output.md)
- [配置参考](docs/reference/config.md)
- [故障排查](docs/reference/errors.md)
- [贡献指南](CONTRIBUTING.md)
- [版本记录](CHANGELOG.md)
- [许可状态](LICENSE)

本仓库尚未选定项目级许可证；LeRobot、PyTorch 等依赖继续适用各自许可。
