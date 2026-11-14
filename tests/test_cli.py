import subprocess
import sys
from pathlib import Path

import pytest

from ai_repo_rules.cli import main
from ai_repo_rules.rendering import OUTPUTS


@pytest.mark.parametrize("agent", ["codex", "claude", "copilot", "all"])
def test_outputs_and_idempotent_updates(tmp_path, agent):
    assert main([str(tmp_path), "--agent", agent]) == 0
    expected = list(OUTPUTS.values()) if agent == "all" else [OUTPUTS[agent]]
    before = {name: (tmp_path / name).read_bytes() for name in expected}
    assert main([str(tmp_path), "--agent", agent, "--update"]) == 0
    assert before == {name: (tmp_path / name).read_bytes() for name in expected}
    assert main([str(tmp_path), "--agent", agent]) == 0
    assert before == {name: (tmp_path / name).read_bytes() for name in expected}


@pytest.mark.parametrize("flag", ["--dry-run", "--diff"])
def test_preview_never_writes(tmp_path, capsys, flag):
    assert main([str(tmp_path), "--agent", "all", flag]) == 0
    assert list(tmp_path.iterdir()) == []
    output = capsys.readouterr().out
    assert "Preview only" in output
    if flag == "--diff":
        assert "+++ b/AGENTS.md" in output
        assert "+# GitHub Copilot instructions" in output


def test_all_conflict_is_preflighted(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("Manual", encoding="utf-8")
    assert main([str(tmp_path), "--agent", "all"]) == 3
    assert not (tmp_path / "AGENTS.md").exists()
    assert not (tmp_path / ".github").exists()


def test_force_preserves_manual_content(tmp_path, capsys):
    path = tmp_path / "AGENTS.md"
    path.write_text("Manual", encoding="utf-8")
    assert main([str(tmp_path), "--force"]) == 0
    assert path.read_text().startswith("Manual")
    assert "deprecated" in capsys.readouterr().err


def test_invalid_path(tmp_path):
    assert main([str(tmp_path / "missing")]) == 2


def test_io_error(tmp_path, monkeypatch):
    def denied(*args):
        raise PermissionError("Denied")

    monkeypatch.setattr("ai_repo_rules.cli.write_changes", denied)
    assert main([str(tmp_path)]) == 4


def test_legacy_entrypoint(tmp_path):
    script = Path(__file__).resolve().parents[1] / "generate_rules.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "AGENTS.md").exists()


def test_runtime_does_not_use_network(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network access forbidden")

    monkeypatch.setattr("socket.socket", forbidden)
    assert main([str(tmp_path), "--agent", "all"]) == 0
