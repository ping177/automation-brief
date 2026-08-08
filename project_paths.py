"""Resolve repository and runtime data paths for automation-brief.

The repository contains code and checked-in examples. Runtime reports, logs,
shadow artifacts, and local holdings live below the canonical data root.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DATA_ROOT_ENV = "AUTOMATION_BRIEF_DATA_ROOT"
PROJECT_ID = "automation-brief"


@dataclass(frozen=True)
class ProjectPaths:
    """Repository-relative and canonical runtime paths."""

    repo_root: Path
    data_root: Path

    @property
    def reports_dir(self) -> Path:
        return self.data_root / "reports"

    @property
    def runs_dir(self) -> Path:
        return self.data_root / "runs"

    @property
    def ai_curator_shadow_dir(self) -> Path:
        return self.runs_dir / "ai-curator-shadow"

    @property
    def log_file(self) -> Path:
        return self.runs_dir / "daily-news.log"

    @property
    def holdings_file(self) -> Path:
        return self.data_root / "manual-inputs" / "holdings.json"

    @property
    def example_holdings_file(self) -> Path:
        return self.repo_root / "config" / "holdings.example.json"

    @property
    def migration_records_dir(self) -> Path:
        return self.data_root / "migration-records"

    def resolve_report_dir(
        self,
        configured_output_dir: str | Path | None = "output",
        explicit_output: Path | None = None,
    ) -> Path:
        """Resolve report output while preserving explicit output overrides.

        ``output`` is the legacy config token and now maps to the canonical
        reports directory. Other configured paths retain their historical
        repository-relative behavior unless they are absolute.
        """

        if explicit_output is not None:
            return Path(explicit_output).expanduser()

        configured = str(configured_output_dir or "").strip()
        if configured in {"", "output", "reports"}:
            return self.reports_dir

        configured_path = Path(configured).expanduser()
        if configured_path.is_absolute():
            return configured_path
        return self.repo_root / configured_path


def get_project_paths(
    *,
    repo_root: Path | None = None,
    data_root: Path | None = None,
) -> ProjectPaths:
    """Return paths using explicit input, environment, then the home default."""

    resolved_repo_root = Path(repo_root or Path(__file__).resolve().parent).expanduser()
    if data_root is None:
        configured_root = os.environ.get(DATA_ROOT_ENV, "").strip()
        data_root = (
            Path(configured_root).expanduser()
            if configured_root
            else Path.home() / "Projects" / "_project-data" / PROJECT_ID
        )
    return ProjectPaths(repo_root=resolved_repo_root, data_root=Path(data_root).expanduser())
