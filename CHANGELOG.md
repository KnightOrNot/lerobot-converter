# Changelog

## Unreleased

- 接入 raw v2 RGB/Z16 PNG 索引、SDK 时间映射校验、逐流目标时间匹配与容差拒绝。
- RGB 输出真实 MP4，深度以无损米制 float32 image 写入，保留旧 raw v1 与 action/observation 配对语义。
- 质量报告增加每路匹配误差、重复帧、SDK 帧号缺口；增加坏图/坏时钟/超限回归和 controller 真实 RGB-D 读回验证。

- 按 controller 文档结构整理架构、安装、CLI、配置、raw schema、输出和排障。
- 更新旧项目目录、GELLO 脚本与自动转换入口，明确 controller 子进程调用边界。
- 新增贡献指南、agent 规范和项目级许可状态；本次不修改转换逻辑。

## 0.1.0

以下汇总现有实现，不表示新增发布 tag。

- 将 `piper_x_gello_raw` v1 session 离线转换为 LeRobot Dataset v3。
- 校验 manifest、七维状态、sequence 与严格递增的 observation 时间戳。
- 基于最近时间戳重采样，支持可选 velocity/末端 feature，忽略 partial episode。
- 拒绝覆盖输出，生成质量报告，并提供可注入 dataset writer 的回归测试。
- 使用 Python 3.12 独立环境和 LeRobot 0.6.1 dataset extra；Linux 使用 PyTorch CPU wheel。
