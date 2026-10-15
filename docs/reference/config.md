# 配置参考

本库没有独立配置文件。CLI、Python API 和 controller 应用配置分别传入参数，不自动共享默认值。

| 选项 | CLI 默认值 | Python `convert_session` |
| --- | --- | --- |
| FPS | `30` | `fps=30` |
| repo ID | `local/<session目录名>` | 必须显式传 `repo_id` |
| velocity | 包含 | `include_velocity=True` |
| 末端位姿 | 包含 | `include_ee_pose=True` |
| 相机误差 | manifest 每路 max_skew_ms | `max_camera_skew_ms=None`；正有限值覆盖 |
| RGB/深度 | 由 raw v2 声明 | RGB video + 无损米制 depth image |

输入/输出路径相对于调用目录，不是仓库目录。controller 调用时可使用自己的 `recording.dataset_fps`、数据路径和 converter 项目路径；这些配置由 controller 解析，再作为参数传来。

LeRobot、Torch 和依赖版本以 `uv.lock` 为准。添加依赖时保持 Python 3.12 环境与 Linux CPU 源约定；不要只改文档中的版本。实际行为和 schema 发生变化时同步更新[数据格式](raw-format.md)、[输出](output.md)和回归测试。
