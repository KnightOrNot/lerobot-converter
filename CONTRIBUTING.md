# 贡献指南

## 环境与职责

使用 Python 3.12 和独立 uv 环境。包元数据允许更高版本；controller 集成固定使用 3.12。

```bash
uv sync --frozen --extra dataset
uv run --extra dataset lerobot-converter --help
```

基础包可解析 CLI 和校验 raw；实际写入和完整测试需要 `dataset` 依赖。保持 LeRobot 延迟导入，不把 PyTorch 引入 controller 的 3.11 进程。安装和系统动态库见[安装指南](docs/installation.md)。

`__init__.py` 负责参数、退出码和报告输出；`converter.py` 负责 manifest/frame 校验、重采样、feature、writer 和质量统计。`DatasetProtocol` 与 `dataset_factory` 允许测试注入 fake writer。设备连接、实时控制、录制和应用退出流程留在 controller/SDK/GELLO。

## 数据与兼容性

raw 是不可变输入，LeRobot 输出可重建。不得为了转换成功修改输入、悄悄跳过坏帧或把 partial 自动转为正式 episode。所有正式 episode 在创建 writer 前校验；输出已存在时拒绝覆盖。

时间轴使用 `observation_time_ns`，保留最近原始样本的整组 action/observation，不分别配对或插值。LeRobot 时间戳是新时间轴，原始纳秒时序保存在 raw。修改时序、字段或采样规则时同步评估 schema 兼容、质量指标和 controller 集成。

关闭可选输出 feature 不应放宽 raw 必填字段校验。未来图像/视频接入需要明确输入 schema、跨流同步和编码约定；当前文档不得描述为已支持。

## 风格与测试

Python 使用四空格、类型标注、`snake_case` 函数/模块和 `PascalCase` 类。Ruff 使用默认规则；没有专用格式化或覆盖率门槛。`--isolated` 避免作为 submodule 时继承父仓库规则，保持独立 checkout 的检查方式。

```bash
uv run --frozen --extra dataset pytest
uv run --frozen --extra dataset ruff check --isolated .
uv build
```

测试使用 `tests/test_*.py`、临时目录和 fake writer，覆盖格式、sequence、时间戳、非有限数、夹爪范围、partial、可选输出、防覆盖与 writer 错误。它们不访问硬件，也不证明真实 LeRobot 数据集兼容。

修改 writer、依赖或 schema 后，在已安装所有环境的 controller 根目录补跑 `uv run --frozen pytest -m integration`，验证实际转换和读回，并说明输入 raw 未改变。无关文档调整无需扩大到硬件测试。

## 提交与文档

历史主题多为简短说明，如 `change project name.`；新提交优先使用 `fix:`、`refactor:`、`docs:` 等前缀和简洁祈使句。PR 写明问题与最终行为、格式/依赖兼容性、检查及真实 writer 验证状态、相关 issue。没有前端变化时无需截图。

先提交、验证并发布本库，再更新 controller gitlink。独立 checkout 与 submodule 不会自动同步。不要提交采集数据、派生数据集、虚拟环境或构建产物。

参数、格式与默认行为变化时更新 README、`docs/reference/`、CHANGELOG 和测试。保留依赖来源与许可声明；当前未选定项目级授权协议。
