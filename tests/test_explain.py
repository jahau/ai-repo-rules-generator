"""Fixture tests for the read-only --explain mode.

Regenerate golden files after an intentional change with:
    UPDATE_GOLDEN=1 python -m pytest tests/test_explain.py
"""

import json
import os
import shutil
from pathlib import Path

import pytest

from ai_repo_rules import detection
from ai_repo_rules.cli import main
from ai_repo_rules.detection import scan
from ai_repo_rules.explain import explain
from ai_repo_rules.generation import block
from ai_repo_rules.rendering import OUTPUTS, render

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN = Path(__file__).resolve().parent / "golden"
NAMES = ["nested-monorepo", "unknown-manifests", "ambiguous-managers"]
CANARY = "FIXTURE_CANARY"
WRITE_FLAGS = ["--dry-run", "--diff", "--update", "--force"]


def run(capsys, *args: str) -> tuple[int, str]:
    code = main([*args])
    return code, capsys.readouterr().out


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def copy(name: str, destination: Path) -> Path:
    target = destination / name
    shutil.copytree(FIXTURES / name, target)
    return target


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("fmt", ["text", "json"])
def test_golden_explanations(capsys, tmp_path, name, fmt):
    # Run from a copy so the golden output also proves location independence.
    project = copy(name, tmp_path)
    code, out = run(capsys, str(project), "--agent", "all", "--explain", "--explain-format", fmt)
    assert code == 0
    golden = GOLDEN / f"{name}.explain.{'txt' if fmt == 'text' else 'json'}"
    if os.environ.get("UPDATE_GOLDEN"):
        golden.parent.mkdir(exist_ok=True)
        golden.write_text(out, encoding="utf-8", newline="\n")
    assert out == golden.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", NAMES)
def test_reproducible_and_location_independent(capsys, tmp_path, name):
    first = copy(name, tmp_path / "one")
    second = copy(name, tmp_path / "another" / "checkout")
    outputs = []
    for project in (first, second, first):
        code, out = run(capsys, str(project), "--explain", "--explain-format", "json")
        assert code == 0
        outputs.append(out)
    assert outputs[0] == outputs[1] == outputs[2]
    assert str(tmp_path) not in outputs[0]
    assert str(tmp_path).replace("\\", "\\\\") not in outputs[0]


@pytest.mark.parametrize("name", NAMES)
def test_every_generated_instruction_is_explained(name):
    result = scan(FIXTURES / name)
    data = explain(result, list(OUTPUTS))
    rendered = {line for agent in OUTPUTS for line in render(result, agent).splitlines()}
    explained = {i["instruction"] for p in data["projects"] for i in p["instructions"]}
    explained |= {w["instruction"] for w in data["warnings"]}
    explained |= {p["heading"] for p in data["projects"]}
    explained |= set(data["template"])
    # Every explained line is a real generated line, and every generated line is explained.
    assert explained <= rendered
    assert rendered - {""} <= explained
    for project in data["projects"]:
        for instruction in project["instructions"]:
            for value in instruction["values"]:
                assert value["observations"], (project["scope"], value)
                assert value["confidence"] in {"high", "medium", "low"}


@pytest.mark.parametrize("name", NAMES)
def test_explain_reads_only_allowlisted_metadata(capsys, monkeypatch, name):
    read: list[str] = []
    original = detection._read

    def recording(path, root, warnings):
        read.append(path.name)
        return original(path, root, warnings)

    monkeypatch.setattr(detection, "_read", recording)
    code, out = run(capsys, str(FIXTURES / name), "--agent", "all", "--explain")
    assert code == 0
    assert set(read) <= {"package.json", "composer.json", "pyproject.toml"}
    assert CANARY not in out


def test_explain_never_plans_or_writes(capsys, tmp_path, monkeypatch):
    project = copy("nested-monorepo", tmp_path)
    # Existing files that normal generation would refuse or rewrite must stay byte-identical.
    (project / "AGENTS.md").write_bytes(b"Manual\r\nrules\r\n")
    (project / "CLAUDE.md").write_bytes(b"\xef\xbb\xbf" + block("Edited\n").encode()[:-5])
    before = snapshot(project)

    def forbidden(*args, **kwargs):
        raise AssertionError("--explain must not plan or write")

    monkeypatch.setattr("ai_repo_rules.cli.plan", forbidden)
    monkeypatch.setattr("ai_repo_rules.cli.write_changes", forbidden)
    code, out = run(capsys, str(project), "--agent", "all", "--explain")
    assert code == 0
    assert "no files were written" in out
    assert snapshot(project) == before
    assert not (project / ".github").exists()


@pytest.mark.parametrize("flag", WRITE_FLAGS)
def test_explain_rejects_write_and_preview_flags(tmp_path, flag):
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path), "--explain", flag])
    assert exc.value.code == 2
    assert list(tmp_path.iterdir()) == []


def test_explain_format_requires_explain(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path), "--explain-format", "json"])
    assert exc.value.code == 2
    assert list(tmp_path.iterdir()) == []


def test_generation_is_unchanged_by_explain(capsys, tmp_path):
    explained = copy("nested-monorepo", tmp_path / "a")
    plain = copy("nested-monorepo", tmp_path / "b")
    assert main([str(explained), "--explain"]) == 0
    assert main([str(explained), "--agent", "all"]) == 0
    assert main([str(plain), "--agent", "all"]) == 0
    for output in OUTPUTS.values():
        assert (explained / output).read_bytes() == (plain / output).read_bytes()


def _scopes(name: str) -> dict[str, dict]:
    data = explain(scan(FIXTURES / name), ["codex"])
    return {p["scope"]: p for p in data["projects"]}


def _values(project: dict, field: str) -> dict[str, dict]:
    return {
        v["value"]: v for i in project["instructions"] if i["field"] == field for v in i["values"]
    }


def test_nested_monorepo_scopes():
    scopes = _scopes("nested-monorepo")
    assert list(scopes) == [
        ".",
        "packages/legacy-cli",
        "packages/ui",
        "services/api",
        "services/api/plugins/payments",
    ]
    # Manifest-less directories belong to the nearest enclosing project, not the root.
    go = _values(scopes["."], "languages")["Go"]
    assert go["confidence"] == "medium"
    assert go["observations"][0]["directories"] == ["tools/codegen"]
    tsx = _values(scopes["packages/ui"], "languages")["TypeScript"]["observations"]
    assert [o["confidence"] for o in tsx] == ["high", "medium"]
    assert tsx[1]["directories"] == ["packages/ui/src", "packages/ui/src/icons/deep"]
    assert "TypeScript" not in _values(scopes["."], "languages")
    # A project nested inside another project keeps its own scope and files.
    payments = scopes["services/api/plugins/payments"]
    assert _values(payments, "commands")["ruff check ."]["confidence"] == "high"
    assert _values(scopes["services/api"], "languages")["Python"]["observations"][1][
        "directories"
    ] == ["services/api/app"]
    # Lockfiles do not propagate from the workspace root to nested packages.
    omitted = _values(scopes["packages/legacy-cli"], "omissions")["package.json scripts"]
    assert "package manager is missing" in omitted["observations"][0]["detail"]


def test_unknown_manifests_are_neither_read_nor_scoped():
    scopes = _scopes("unknown-manifests")
    assert list(scopes) == [".", "known"]
    text = json.dumps(explain(scan(FIXTURES / "unknown-manifests"), ["codex"]))
    for unknown in ("deno.json", "mix.exs", "Makefile", "pubspec.yaml", "mobile"):
        assert unknown not in text
    root = scopes["."]
    assert _values(root, "scope")["."]["observations"][0]["detail"].startswith("repository root")
    assert _values(root, "languages")["TypeScript"]["confidence"] == "medium"
    assert _values(root, "frameworks")["WordPress"]["confidence"] == "low"


def test_ambiguous_managers_are_explained_not_guessed():
    scopes = _scopes("ambiguous-managers")
    details = {
        scope: _values(scopes[scope], "omissions")["package.json scripts"]["observations"][0][
            "detail"
        ]
        for scope in ("two-lockfiles", "field-vs-lockfile", "no-manager")
    }
    assert "ambiguous (npm, yarn)" in details["two-lockfiles"]
    assert "ambiguous (pnpm, yarn)" in details["field-vs-lockfile"]
    assert "missing" in details["no-manager"]
    for scope in details:
        assert not _values(scopes[scope], "commands")
    agreeing = scopes["agreeing"]
    yarn = _values(agreeing, "managers")["yarn"]["observations"]
    assert [o["source"] for o in yarn] == ["agreeing/package.json", "agreeing/yarn.lock"]
    assert _values(agreeing, "commands")["yarn run test"]["confidence"] == "medium"


def test_omission_is_explained_even_when_other_commands_exist(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts":{"test":"x"}}', encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("", encoding="utf-8")
    (tmp_path / "yarn.lock").write_text("", encoding="utf-8")
    (tmp_path / "composer.json").write_text('{"scripts":{"test":"x"}}', encoding="utf-8")
    result = scan(tmp_path)
    root = {p["scope"]: p for p in explain(result, ["codex"])["projects"]}["."]
    omission = [i for i in root["instructions"] if i["field"] == "omissions"]
    assert (
        omission[0]["instruction"] == "- `.: package manager missing or ambiguous; scripts omitted`"
    )
    assert omission[0]["instruction"] in render(result, "codex").splitlines()
    assert "ambiguous (npm, yarn)" in omission[0]["values"][0]["observations"][0]["detail"]
    assert "composer run-script test" in _values(root, "commands")


def test_warnings_use_posix_paths(tmp_path):
    (tmp_path / "packages" / "a").mkdir(parents=True)
    (tmp_path / "packages" / "a" / "package.json").write_text("{", encoding="utf-8")
    assert "Invalid configuration: packages/a/package.json" in scan(tmp_path).warnings


def test_text_explain_survives_non_utf8_stdout(tmp_path):
    import subprocess
    import sys

    (tmp_path / "日本").mkdir()
    (tmp_path / "日本" / "package.json").write_text("{}", encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    result = subprocess.run(
        [sys.executable, "-m", "ai_repo_rules", str(tmp_path), "--explain"],
        capture_output=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert rb"\u65e5\u672c" in result.stdout


def test_closed_pipe_is_not_reported_as_io_failure(tmp_path, monkeypatch, capsys):
    import io

    class ClosedPipe:
        encoding = "utf-8"

        def write(self, text):
            raise BrokenPipeError

        def flush(self):
            pass

        def isatty(self):
            return False

        def fileno(self):
            # Like a captured stream; Python 3.14 argparse probes this for color support.
            raise io.UnsupportedOperation("fileno")

    monkeypatch.setattr("sys.stdout", ClosedPipe())
    assert main([str(tmp_path), "--explain"]) == 1
    assert "I/O error" not in capsys.readouterr().err
