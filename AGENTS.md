# Repository Guidelines

## Project Structure & Responsibilities

`src/lerobot_converter/__init__.py` owns CLI parsing, exit codes, and report output. `converter.py` validates raw v1 sessions, resamples observation timestamps, writes LeRobot Dataset v3, and reports quality. `tests/` uses temporary sessions and fake writers; `docs/` contains architecture, installation, schema, CLI, and troubleshooting references.

Keep hardware, real-time following, recording, and process orchestration in SDK/GELLO/controller. This converter reads immutable raw input and writes a new derived dataset. Camera and video ingestion are not implemented. Do not add hardware imports or make controller import LeRobot into its Python process.

## Build, Test, and Development Commands

Use Python 3.12 and an independent uv environment from this repository root.

- `uv sync --frozen --extra dataset`: install the real writer and development dependencies.
- `uv run --frozen --extra dataset lerobot-converter --help`: inspect arguments without conversion.
- `uv run --frozen --extra dataset pytest`: run unit regressions with fake dataset writers.
- `uv run --frozen --extra dataset ruff check --isolated .`: run standalone default lint.
- `uv build`: build distributions.

The lightweight base package can validate raw without LeRobot; full tests and writing require dataset dependencies. Writer/schema changes also require the controller's real conversion/readback integration test: `uv run --frozen pytest -m integration` from its root with all environments installed.

## Coding & Testing Guidelines

Use four spaces, annotated interfaces, snake_case functions/modules, and PascalCase classes. Tests use `test_*.py`; no coverage threshold or dedicated formatter is configured. Ruff has no repository configuration; use `--isolated` to avoid inheriting a parent checkout's rules. Inject `dataset_factory` to test validation, timestamp matching, optional features, writer failures, partial episodes, and output protection.

Never mutate raw or overwrite an existing output directory. Reject invalid completed episodes rather than silently dropping rows. Preserve action/observation pairs when resampling; LeRobot timestamps describe the new timeline. Optional output flags do not relax raw schema validation. Successful reports are not corruption-repair summaries. Unit tests do not establish real writer compatibility.

## Commits & Pull Requests

Prefer concise imperative subjects with conventional prefixes. Explain data-contract changes, dependency compatibility, checks, real writer validation, and related issues. Update README, reference docs, and CHANGELOG together.

Publish tested converter commits before updating parent gitlinks. Standalone and submodule checkouts are independent. Do not commit datasets, environments, caches, or build artifacts. No project-wide license has been selected; preserve third-party notices without inventing a license grant.
