# 安装指南

## Python 与依赖

使用独立 Python 3.12 环境。准备 Git、pyenv、uv 后，在本仓库根目录执行：

```bash
converter_requested_version="$(<.python-version)"
converter_resolved_version="$(pyenv latest -k "$converter_requested_version")"
pyenv install -s "$converter_resolved_version"
converter_python="$(PYENV_VERSION="$converter_resolved_version" pyenv which python)"
UV_NO_MANAGED_PYTHON=1 uv sync --frozen --extra dataset --python "$converter_python"
```

已有 Python 3.12 时通常只需 `uv sync --frozen --extra dataset`。基础包没有运行依赖，支持 CLI 帮助和标准库 raw 校验；实际转换与完整测试需要 dataset extra，其中包含 LeRobot 0.6.1、NumPy、PyTorch 等。Linux 的 torch/torchvision 从锁定的 CPU wheel 源安装，不需要 CUDA。

作为 controller submodule 时，可用根项目 `scripts/setup.sh` 统一准备；controller 的 3.11 环境不安装 LeRobot。

## 系统视频库

当前没有视频输入，但所选 LeRobot 环境可能加载 TorchCodec。Ubuntu 使用系统 FFmpeg 提供其动态库：

```bash
sudo apt update
sudo apt install -y ffmpeg
sudo ldconfig
ffmpeg -version
```

不要用同名 Python `ffmpeg` 包替代系统共享库。安装后验证：

```bash
uv run --extra dataset python -c "from torchcodec.decoders import VideoDecoder; print('TorchCodec loaded')"
uv run --extra dataset python -c "from lerobot.utils.import_utils import get_safe_default_video_backend; print(get_safe_default_video_backend())"
uv run --extra dataset lerobot-converter --help
```

锁定环境正常加载时默认后端为 `torchcodec`。如果报缺失 `libav*.so`，按[排障指南](reference/errors.md)区分 Python 依赖与系统库；反复重建 `.venv` 不能补齐系统共享库。通过该检查不表示本转换器已支持视频。

## 输入准备

输入需有 manifest 和至少一个已保存 episode，结构见 [Raw v1](reference/raw-format.md)。controller 采集时按 S 正式保存；partial 不会自动恢复为正式集。实际转换只需要两个路径，见 [CLI](reference/cli.md)。
