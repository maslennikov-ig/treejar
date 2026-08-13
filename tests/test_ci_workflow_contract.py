from __future__ import annotations

import shlex
from pathlib import Path

import pytest
import yaml


def _load_ci_workflow():
    return yaml.load(
        Path(".github/workflows/ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )


def _assert_test_job_fetches_full_history(workflow) -> None:
    test_job = workflow["jobs"]["test"]
    run_test_steps = [
        step for step in test_job["steps"] if step.get("name") == "Run tests"
    ]
    assert len(run_test_steps) == 1
    assert shlex.split(run_test_steps[0]["run"]) == [
        "uv",
        "run",
        "pytest",
        "tests/",
        "-v",
        "--tb=short",
    ]

    checkout_steps = [
        step
        for step in test_job["steps"]
        if step.get("uses", "").startswith("actions/checkout@")
    ]

    assert len(checkout_steps) == 1
    assert checkout_steps[0].get("with", {}).get("fetch-depth") == "0"


def test_ci_workflow_skips_docs_and_orchestration_only_changes() -> None:
    workflow = _load_ci_workflow()

    expected_ignored_paths = {
        ".codex/**",
        ".beads/**",
        "docs/**",
        "**/*.md",
    }

    push_ignored_paths = set(workflow["on"]["push"].get("paths-ignore", []))
    pull_request_ignored_paths = set(
        workflow["on"]["pull_request"].get("paths-ignore", [])
    )

    assert expected_ignored_paths.issubset(push_ignored_paths)
    assert expected_ignored_paths.issubset(pull_request_ignored_paths)

    assert "changes" in workflow["jobs"]
    assert "changes" in workflow["jobs"]["deploy"]["needs"]
    assert "needs.changes.outputs.deploy == 'true'" in workflow["jobs"]["deploy"]["if"]


def test_ci_test_job_fetches_full_history_for_scope_provenance() -> None:
    workflow = _load_ci_workflow()

    _assert_test_job_fetches_full_history(workflow)


def test_the_pgvector_retrieval_claim_has_an_automatic_gate() -> None:
    """`tj-qfsy`. The central `tj-rcg5` claim had no gate at all.

    One test exercises it -- the producer going through
    `src.rag.pipeline.search_products` on real exact pgvector, with no ANN
    index and no database residue -- and it skips itself whenever
    `SEMANTIC_EVIDENCE_DATABASE_URL` is unset, which is CI and every default
    local run. The audit had to reproduce it by hand on a throwaway container.
    """

    workflow = _load_ci_workflow()
    job = workflow["jobs"]["semantic-evidence"]

    assert "pgvector/pgvector" in job["services"]["pgvector"]["image"]
    database_url = job["env"]["SEMANTIC_EVIDENCE_DATABASE_URL"]
    assert database_url.startswith("postgresql+asyncpg://")
    # `_validate_local_database_url` refuses anything else.
    assert "@127.0.0.1:" in database_url
    assert "/treejar_semantic_evidence" in database_url

    run_steps = [
        step
        for step in job["steps"]
        if step.get("name") == "Run the pgvector retrieval integration test"
    ]

    assert len(run_steps) == 1
    command = run_steps[0]["run"]
    assert "test_producer_runs_pinned_bge_through_real_exact_pgvector_search" in command
    # A skipped test reports success. That is the exact shape of the hole this
    # job closes, so the step has to read the outcome rather than the exit code.
    assert "1 passed" in command


def test_the_pinned_model_is_fetched_before_a_run_that_cannot_fetch_it() -> None:
    """`PinnedEmbeddingEngine` passes `local_files_only=True`.

    The pin is offline by design: it never downloads, it only reads what is
    already in `HF_HOME`. The first run of this job proved it -- an empty cache
    failed in 1.7s with "couldn't connect to huggingface.co", because nothing
    had put the model there. The fetch step and the cache have to name the same
    revision, or the cache key promises a model the fetch does not place.
    """

    workflow = _load_ci_workflow()
    steps = workflow["jobs"]["semantic-evidence"]["steps"]
    names = [step.get("name") for step in steps]

    assert names.index("Fetch the pinned embedding model") < names.index(
        "Run the pgvector retrieval integration test"
    )

    fetch = steps[names.index("Fetch the pinned embedding model")]["run"]
    cache = next(
        step for step in steps if step.get("name") == "Cache the pinned embedding model"
    )
    revision = "5617a9f61b028005a4858fdac845db406aefb181"

    assert revision in fetch
    assert revision in cache["with"]["key"]
    # Verified against the loader rather than guessed: the suite passes with
    # `onnx/` absent, and every other file in the pinned snapshot is fetched.
    assert "pytorch_model.bin" in fetch
    assert "onnx" not in fetch


def test_the_semantic_gate_runs_on_every_change_to_what_it_guards() -> None:
    workflow = _load_ci_workflow()
    classify = "".join(
        step["run"]
        for step in workflow["jobs"]["changes"]["steps"]
        if step.get("id") == "classify"
    )

    assert "scripts/corpus_bridge/" in classify
    assert "src/rag/" in classify
    assert "semantic=true" in classify
    assert "semantic=false" in classify

    job = workflow["jobs"]["semantic-evidence"]

    assert "changes" in job["needs"]
    assert "needs.changes.outputs.semantic == 'true'" in job["if"]
    assert workflow["jobs"]["changes"]["outputs"]["semantic"]


def test_ci_full_test_command_contract_rejects_narrowed_command() -> None:
    workflow = _load_ci_workflow()
    run_test_steps = [
        step
        for step in workflow["jobs"]["test"]["steps"]
        if step.get("name") == "Run tests"
    ]

    assert len(run_test_steps) == 1
    run_test_steps[0]["run"] = "uv run pytest tests/test_ci_workflow_contract.py -q"

    with pytest.raises(AssertionError):
        _assert_test_job_fetches_full_history(workflow)
