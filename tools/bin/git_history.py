#!/usr/bin/env python3
"""Auto-commit KML changes and session-scoped undo."""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitHistory:
    def __init__(self, repo_root: Path, kml_path: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.kml_path = kml_path.resolve()
        self.session_commits = 0
        self._rel_kml = self._relative(kml_path)

    def _relative(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.repo_root))
        except ValueError:
            return str(path)

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

    def commit_move(self, codes: list[str]) -> bool:
        if not codes:
            return False
        add = self._run("git", "add", self._rel_kml)
        if add.returncode != 0:
            return False
        msg = f"CircleCity: move {', '.join(codes)}"
        commit = self._run("git", "commit", "-m", msg)
        if commit.returncode != 0:
            if "nothing to commit" in (commit.stdout + commit.stderr).lower():
                return False
            print(f"git commit failed: {commit.stderr.strip()}", flush=True)
            return False
        self.session_commits += 1
        return True

    def undo(self) -> bool:
        if self.session_commits <= 0:
            return False
        reset = self._run("git", "reset", "--hard", "HEAD~1")
        if reset.returncode != 0:
            print(f"git undo failed: {reset.stderr.strip()}", flush=True)
            return False
        self.session_commits -= 1
        return True

    @property
    def undos_available(self) -> int:
        return self.session_commits