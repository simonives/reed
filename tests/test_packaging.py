# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


class TestPackagingDependencyResolution:
    def test_fresh_pip_install_resolves_lxml_html_clean_extra(self, tmp_path):
        """The Dockerfile runs `pip install .` with no lockfile — pip's
        resolver does not reliably merge the lxml[html-clean] extra that
        justext (a transitive dep of trafilatura) requires when another
        package in the tree also requires bare lxml. This must be pinned
        explicitly in pyproject.toml so a fresh install is deterministic."""
        venv_dir = tmp_path / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        pip = venv_dir / "bin" / "pip"
        install = subprocess.run(
            [str(pip), "install", "--no-cache-dir", str(REPO_ROOT)],
            capture_output=True,
            text=True,
        )
        assert install.returncode == 0, install.stderr

        python = venv_dir / "bin" / "python"
        result = subprocess.run(
            [str(python), "-c", "import reed.reader"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
