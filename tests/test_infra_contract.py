from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_infra_build_contract_uses_locked_uv_and_cpu_torch() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text()
    ci_workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    pyproject = (REPO_ROOT / "pyproject.toml").read_text()
    uv_lock = (REPO_ROOT / "uv.lock").read_text()

    assert "ghcr.io/astral-sh/uv:latest" not in dockerfile
    assert "ghcr.io/astral-sh/uv:0.11.6" not in dockerfile
    assert (
        "ghcr.io/astral-sh/uv@sha256:b1e699368d24c57cda93c338a57a8c5a119009ba809305cc8e86986d4a006754"
        in dockerfile
    )
    assert "RUN UV_NO_DEV=1 uv sync --locked" in dockerfile
    assert "RUN UV_NO_DEV=1 uv sync --locked --no-install-project" in dockerfile
    assert "pip install --no-cache-dir" not in dockerfile

    assert 'uv pip install --system -e ".[dev]"' not in ci_workflow
    assert 'version: "0.11.6"' in ci_workflow
    assert "uv sync --locked --all-extras --dev" in ci_workflow
    assert "uv run ruff check src/ tests/" in ci_workflow
    assert "uv run ruff format --check src/ tests/" in ci_workflow
    assert "uv run mypy src/" in ci_workflow
    assert "uv run pytest tests/ -v --tb=short" in ci_workflow

    assert "[tool.uv.sources]" in pyproject
    assert 'torch = { index = "pytorch-cpu" }' in pyproject
    assert "https://download.pytorch.org/whl/cpu" in pyproject
    assert "explicit = true" in pyproject

    assert 'name = "cuda-' not in uv_lock
    assert 'name = "nvidia-' not in uv_lock
