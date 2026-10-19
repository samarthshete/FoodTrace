"""Spec-driven development guard: specs and tests must agree (specs/README.md)."""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = ROOT / "specs"
TEST_DIR = Path(__file__).resolve().parent
REQ = re.compile(r"^- \*\*([A-Z]+-\d+)\*\*", re.MULTILINE)
RETIRED = re.compile(r"^- ~~\*\*([A-Z]+-\d+)\*\*", re.MULTILINE)
STATUS = re.compile(r"^Status: (\w+)", re.MULTILINE)


def spec_requirements() -> dict[str, set[str]]:
    """Requirement IDs by status, from every specs/NNN-*.md file."""
    by_status: dict[str, set[str]] = {}
    for path in sorted(SPEC_DIR.glob("[0-9][0-9][0-9]-*.md")):
        text = path.read_text()
        match = STATUS.search(text)
        assert match, f"{path.name} has no 'Status:' line"
        by_status.setdefault(match.group(1), set()).update(REQ.findall(text))
    return by_status


WEB_TESTS = ROOT / "web"
WEB_TEST_GLOBS = ("src/**/*.test.ts", "src/**/*.test.tsx", "e2e/**/*.spec.ts")
WEB_ID = re.compile(r"\[([A-Z]+-\d+)\]")


def _web_tested_ids() -> set[str]:
    """IDs cited in web test titles, e.g. it("[SCAN-5] accepts ...")."""
    ids: set[str] = set()
    for pattern in WEB_TEST_GLOBS:
        for path in WEB_TESTS.glob(pattern):
            if "node_modules" not in path.parts:
                ids.update(WEB_ID.findall(path.read_text()))
    return ids


def _tested_ids() -> set[str]:
    """IDs referenced by @spec(...) under api/tests, plus IDs cited in web test titles."""
    ids: set[str] = _web_tested_ids()
    for path in TEST_DIR.rglob("test_*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            # @pytest.mark.spec(...) or the module alias @spec(...)
            if (isinstance(func, ast.Attribute) and func.attr == "spec") or (
                isinstance(func, ast.Name) and func.id == "spec"
            ):
                ids.update(
                    a.value
                    for a in node.args
                    if isinstance(a, ast.Constant) and isinstance(a.value, str)
                )
    return ids


def test_every_requirement_has_a_test() -> None:
    reqs = spec_requirements()
    enforced = reqs.get("approved", set()) | reqs.get("implemented", set())
    untested = sorted(enforced - _tested_ids())
    assert not untested, f"Requirements with no test: {untested}"


def test_every_spec_marker_points_at_a_real_requirement() -> None:
    known = set().union(*spec_requirements().values())
    unknown = sorted(_tested_ids() - known)
    assert not unknown, f"Tests reference unknown requirement IDs: {unknown}"


def test_requirement_ids_are_unique() -> None:
    seen: dict[str, str] = {}
    for path in sorted(SPEC_DIR.glob("[0-9][0-9][0-9]-*.md")):
        for rid in REQ.findall(path.read_text()):
            assert rid not in seen, f"{rid} is defined in both {seen[rid]} and {path.name}"
            seen[rid] = path.name
