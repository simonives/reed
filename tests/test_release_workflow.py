# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

RELEASE_WORKFLOW = Path(__file__).parent.parent / ".github" / "workflows" / "release.yml"
COMPOSE_FILE = Path(__file__).parent.parent / "docker-compose.yml"


def _load_release_workflow() -> dict[str, Any]:
    return yaml.safe_load(RELEASE_WORKFLOW.read_text())


def _get_on_block(workflow: dict[str, Any]) -> dict[str, Any]:
    """PyYAML's default (YAML 1.1) resolver parses the bare key `on` as the
    boolean True, not the string "on" — verified against this exact file.
    Every test needing the trigger block must go through this helper."""
    return workflow.get("on", workflow.get(True, {}))


def _find_step(workflow: dict[str, Any], step_name: str) -> dict[str, Any]:
    steps = workflow["jobs"]["release"]["steps"]
    for step in steps:
        if step.get("name") == step_name:
            return step
    raise AssertionError(f"No step named {step_name!r} found in release.yml")


class TestPyPIPublishAuth:
    def test_publish_step_does_not_use_a_password_secret(self):
        """Publish to PyPI must rely on OIDC trusted publishing (the
        `id-token: write` permission already declared at the workflow
        level), not a `password`/token secret — the workflow previously
        declared both, which is inconsistent: trusted publishing takes over
        automatically when no password is supplied."""
        workflow = _load_release_workflow()
        step = _find_step(workflow, "Publish to PyPI")
        with_block = step.get("with") or {}
        assert "password" not in with_block
        assert workflow["permissions"]["id-token"] == "write"


class TestDockerComposeRequiredApiKey:
    def test_compose_config_fails_loudly_without_api_key(self):
        """docker-compose.yml previously hardcoded REED_API_KEY: "change-me"
        as a default, so `docker compose up` would silently start with a
        known, publicly-documented credential if the user never set their
        own. It must now fail immediately with a clear message instead.

        `--env-file /dev/null` is required here: Compose auto-loads a `.env`
        file sitting beside the compose file, and README.md's own quickstart
        (`cp .env.example .env`) means any developer following it would have
        exactly that file present — which would silently supply the key and
        make this test pass for the wrong reason (or rather, fail to catch a
        real regression) regardless of whether the hardcoded default has
        actually been removed."""
        env = {k: v for k, v in os.environ.items() if k != "REED_API_KEY"}
        result = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "--env-file", "/dev/null", "config"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode != 0
        assert "REED_API_KEY" in result.stderr

    def test_compose_config_succeeds_with_api_key_set(self):
        env = {**os.environ, "REED_API_KEY": "test-key-123"}
        result = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "config"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0
        assert "test-key-123" in result.stdout


class TestPythonVersionConsistency:
    def test_release_workflow_python_version_matches_mypy_target(self):
        """release.yml previously pinned Python 3.12 while ci.yml and
        pyproject.toml's [tool.mypy] python_version both target 3.11 —
        under 3.12, mypy resolves a numpy version whose stubs use
        3.12-only syntax and fails against the 3.11 target. Reproduced
        locally: same resolved deps pass under 3.11, fail under 3.12."""
        workflow = _load_release_workflow()
        step = _find_step(workflow, "Set up Python")
        assert step["with"]["python-version"] == "3.11"


class TestDryRunTrigger:
    def test_workflow_dispatch_trigger_has_dry_run_input_defaulting_true(self):
        workflow = _load_release_workflow()
        on_block = _get_on_block(workflow)
        assert "workflow_dispatch" in on_block
        dry_run_input = on_block["workflow_dispatch"]["inputs"]["dry_run"]
        assert dry_run_input["type"] == "boolean"
        assert dry_run_input["default"] is True

    def test_tag_push_trigger_is_unchanged(self):
        """The real release trigger (a v*.*.* tag push) must still exist
        and be untouched by adding workflow_dispatch."""
        workflow = _load_release_workflow()
        on_block = _get_on_block(workflow)
        assert on_block["push"]["tags"] == ["v*.*.*"]

    def test_publish_and_release_steps_are_gated_on_real_tag_push_only(self):
        """These steps must run ONLY on a real `v*.*.*` tag push — never on
        workflow_dispatch, regardless of the dry_run input's value. An
        earlier version gated on `dry_run == false`, which meant unchecking
        the dry_run box on a workflow_dispatch run (from any branch, no tag
        involved) would publish to PyPI and create a GitHub Release. PyPI
        publishes are irreversible, so the condition is checked for the
        exact expression, not a loose substring match that would also pass
        if the logic were inverted."""
        workflow = _load_release_workflow()
        expected = "github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')"
        for step_name in ("Publish to PyPI", "Create GitHub Release"):
            step = _find_step(workflow, step_name)
            assert step.get("if", "").strip() == expected

    def test_publish_to_pypi_skips_existing_to_survive_a_retry(self):
        """If a later step (e.g. Create GitHub Release) fails after PyPI
        publish already succeeded, re-running the workflow on the same tag
        must not fail with 'File already exists' — skip-existing makes the
        publish step idempotent."""
        workflow = _load_release_workflow()
        step = _find_step(workflow, "Publish to PyPI")
        assert step.get("with", {}).get("skip-existing") is True

    def test_docker_metadata_latest_and_dryrun_tags_are_not_swapped(self):
        """Without an explicit `enable` guard, `type=raw,value=latest` would
        apply on every trigger including workflow_dispatch (which has no
        git tag ref for the semver patterns to resolve against), so a dry
        run would silently overwrite the real :latest GHCR tag. Checked for
        the exact `enable=` expression on each tag line, not just substring
        presence, so swapping which trigger each tag is enabled on — the
        specific failure mode this guards against — cannot pass silently."""
        workflow = _load_release_workflow()
        step = _find_step(workflow, "Docker metadata")
        tags = step["with"]["tags"]
        assert "type=raw,value=latest,enable=${{ github.event_name == 'push' }}" in tags
        assert (
            "type=raw,value=dryrun-{{sha}},enable=${{ github.event_name == 'workflow_dispatch' }}"
            in tags
        )


class TestApplicationSbomGeneration:
    def test_cyclonedx_py_environment_flags_are_valid(self, tmp_path):
        """release.yml previously passed --outfile to `cyclonedx-py
        environment`, but the installed cyclonedx-bom has no such flag
        (it's -o/--output-file) — confirmed via a live GitHub Actions run
        that failed with 'unrecognized arguments: --outfile' (exit code 2).
        This test runs the exact command shape release.yml uses, so a
        wrong flag name fails the same way here as it does in CI."""
        workflow = _load_release_workflow()
        step = _find_step(workflow, "Generate application SBOM")
        run_script = step["run"]
        assert "--outfile" not in run_script

        output_file = tmp_path / "sbom.json"
        result = subprocess.run(
            [
                "cyclonedx-py",
                "environment",
                "--output-format",
                "json",
                "--output-file",
                str(output_file),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert output_file.exists()

        sbom = json.loads(output_file.read_text())
        assert sbom["bomFormat"] == "CycloneDX"


class TestRefNameSanitization:
    def test_sbom_filenames_do_not_interpolate_raw_ref_name(self):
        """github.ref_name is a tag on a real release (safe: 'v1.0.0',
        no special characters) but a branch name on workflow_dispatch —
        and this repo's branch convention (feat/, fix/, docs/, chore/)
        always contains a '/', which breaks as a literal path separator
        in an output filename. Confirmed live: run 31862631150 failed at
        Generate application SBOM with exactly this defect on branch
        feat/m7-distribution-sbom. Every filename-producing step must use
        a sanitized ref, never github.ref_name directly.

        No step is exempted from the `run:` check, including the
        sanitization step itself — it must receive the raw ref via an
        `env:` var, not by interpolating `${{ github.ref_name }}` directly
        into its shell command. A ref name containing a single quote (a
        legal git branch character) would otherwise let a maintainer with
        push access break out of the quoted string and inject arbitrary
        shell into a job holding `id-token: write` and `packages: write`."""
        workflow = _load_release_workflow()
        steps = workflow["jobs"]["release"]["steps"]
        for step in steps:
            run_script = step.get("run", "")
            assert "${{ github.ref_name }}" not in run_script, (
                f"step {step.get('name')!r} interpolates raw github.ref_name "
                "into a shell command — sanitize it first"
            )
            with_block = step.get("with") or {}
            for key, value in with_block.items():
                if isinstance(value, str):
                    assert "${{ github.ref_name }}" not in value, (
                        f"step {step.get('name')!r}'s {key!r} input "
                        "interpolates raw github.ref_name — sanitize it first"
                    )

    def test_sanitize_ref_step_receives_ref_via_env_and_replaces_slashes(self):
        """The raw ref must arrive via `env:`, never inlined into `run:`
        (see the injection scenario above), and the shell logic must
        replace '/' — the specific character responsible for the live
        failure — with a filesystem-safe substitute."""
        workflow = _load_release_workflow()
        step = _find_step(workflow, "Compute safe ref name")
        assert step["id"] == "ref"
        assert step.get("env", {}).get("REF_NAME") == "${{ github.ref_name }}"
        assert r"${REF_NAME//\//-}" in step["run"]
