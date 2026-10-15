# 开发与调试文档导航

原手册按用途拆分，旧路径保留为导航入口。

- [贡献指南与测试](../CONTRIBUTING.md)
- [架构与时间重采样](index.md)
- [环境和 FFmpeg](installation.md)
- [CLI](reference/cli.md)
- [Raw v1 完整约定](reference/raw-format.md)
- [Dataset v3 输出和质量报告](reference/output.md)
- [配置](reference/config.md)
- [排障](reference/errors.md)

采集端已迁入 controller；使用 `scripts/start_data_record.sh`，不再调用旧 GELLO `piper_x_follow_record.py`。controller 在独立 Python 3.12 子进程调用 converter，不共享硬件进程解释器。
