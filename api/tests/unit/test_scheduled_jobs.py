from pathlib import Path
from typing import Any

import pytest
import yaml

spec = pytest.mark.spec
WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "data-refresh.yml"


@pytest.fixture(scope="module")
def wf() -> dict[Any, Any]:
    data: dict[Any, Any] = yaml.safe_load(WORKFLOW.read_text())
    return data


def runs(job: dict[str, Any]) -> str:
    return "\n".join(step.get("run", "") for step in job["steps"])


@spec("OPS-1")
def test_daily_recalls_and_weekly_full_refresh(wf: dict[Any, Any]) -> None:
    triggers = wf[True]  # YAML 1.1 reads the `on:` key as True
    assert [c["cron"] for c in triggers["schedule"]] == ["17 7 * * *", "23 6 * * 1"]
    assert "workflow_dispatch" in triggers
    assert "17 7 * * *" in wf["jobs"]["recalls"]["if"] and "23 6 * * 1" in wf["jobs"]["full"]["if"]
    assert "pipeline.recalls" in runs(wf["jobs"]["recalls"])
    full = runs(wf["jobs"]["full"])
    order = ["alembic upgrade head", "pipeline.reference --refresh", "pipeline.off_bulk --refresh",
             "pipeline.recalls"]  # fmt: skip
    assert [full.index(c) for c in order] == sorted(full.index(c) for c in order)


@spec("OPS-2", "OPS-5")
def test_jobs_skip_quietly_without_a_database(wf: dict[Any, Any]) -> None:
    for job in wf["jobs"].values():
        first = job["steps"][0]
        assert first["id"] == "setup" and "skipped: no DATABASE_URL secret" in first["run"]
        assert all(s.get("if") == "steps.setup.outputs.ready == 'true'" for s in job["steps"][1:])
        assert job["env"]["DATABASE_URL"] == "${{ secrets.DATABASE_URL }}"


@spec("OPS-3")
def test_usda_is_optional_in_the_weekly_job(wf: dict[Any, Any]) -> None:
    full = wf["jobs"]["full"]
    assert full["env"]["USDA_BRANDED_ZIP_URL"] == "${{ vars.USDA_BRANDED_ZIP_URL }}"
    assert "importing Open Food Facts alone" in runs(full)


@spec("OPS-4", "OPS-6")
def test_no_overlap_timeouts_and_least_privilege(wf: dict[Any, Any]) -> None:
    assert wf["concurrency"] == {"group": "data-refresh", "cancel-in-progress": False}
    assert wf["permissions"] == {"contents": "read"}
    assert wf["jobs"]["recalls"]["timeout-minutes"] == 20
    assert wf["jobs"]["full"]["timeout-minutes"] == 90
    for job in wf["jobs"].values():
        secrets = [v for v in job["env"].values() if "secrets." in v]
        assert secrets == ["${{ secrets.DATABASE_URL }}"]
        assert "continue-on-error" not in job  # a failure fails the run, so GitHub notifies
