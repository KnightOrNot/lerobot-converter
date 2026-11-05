# 贡献与开发检查

## 规则

- 转换只依赖 raw，不访问硬件。
- 新增默认值写入 `config/default.toml`；CLI 参数优先。
- 保持目标目录“不存在才写”的语义，不覆盖已有数据集。
- 不提交 raw、数据集、`.venv` 或模型缓存。

## 检查

```bash
uv python install 3.12
uv sync --frozen --extra dataset
uv run --frozen --extra dataset pytest -q
uv run --frozen ruff check src tests
```

涉及 LeRobot 写入的改动需要真实 dataset extra 的回归测试；
离线测试通过不代表实际视频编码和存储吞吐已验证。
