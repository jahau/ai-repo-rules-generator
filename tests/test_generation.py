import os

import pytest

from ai_repo_rules.generation import Conflict, block, plan, write_changes


def test_default_never_overwrites(tmp_path):
    path = tmp_path / "AGENTS.md"
    path.write_bytes(b"Manual\r\n")
    with pytest.raises(Conflict, match="already exists"):
        plan(tmp_path, "AGENTS.md", "Generated\n", False)
    assert path.read_bytes() == b"Manual\r\n"


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_preserves_manual_prefix_suffix_and_newlines(tmp_path, newline):
    path = tmp_path / "AGENTS.md"
    prefix = "\ufeff# Manual" + newline * 2
    suffix = newline + "My rules" + newline
    path.write_bytes((prefix + block("Old\n").replace("\n", newline) + suffix).encode())
    change = plan(tmp_path, "AGENTS.md", "New\n", True)
    write_changes(tmp_path, [change])
    assert path.read_bytes() == (prefix + block("New\n").replace("\n", newline) + suffix).encode()
    assert not plan(tmp_path, "AGENTS.md", "New\n", True).changed


def test_appends_to_manual_only_file(tmp_path):
    path = tmp_path / "CLAUDE.md"
    path.write_bytes(b"Manual without newline")
    write_changes(tmp_path, [plan(tmp_path, "CLAUDE.md", "Generated\n", True)])
    assert path.read_bytes().startswith(b"Manual without newline\n\n")


@pytest.mark.parametrize(
    "content",
    [
        block("Old\n").replace("Old", "Edited"),
        block("Old\n") * 2,
        "<!-- ai-repo-rules:begin -->\n",
        "<!-- ai-repo-rules:end -->\n",
        "<!-- ai-repo-rules:end -->\n" + block("Old\n").split("<!-- ai-repo-rules:end")[0],
    ],
)
def test_modified_or_malformed_blocks_conflict(tmp_path, content):
    path = tmp_path / "AGENTS.md"
    path.write_text(content, encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(Conflict):
        plan(tmp_path, "AGENTS.md", "New\n", True)
    assert path.read_bytes() == before


def test_changed_since_planning_is_preserved(tmp_path):
    change = plan(tmp_path, "AGENTS.md", "New\n", False)
    change.path.write_text("Concurrent edit", encoding="utf-8")
    with pytest.raises(Conflict, match="changed since planning"):
        write_changes(tmp_path, [change])
    assert change.path.read_text() == "Concurrent edit"


def test_non_utf8_conflict(tmp_path):
    (tmp_path / "AGENTS.md").write_bytes(b"\xff")
    with pytest.raises(Conflict, match="UTF-8"):
        plan(tmp_path, "AGENTS.md", "New\n", True)


def test_hardlink_rejected(tmp_path):
    source = tmp_path / "manual.md"
    source.write_text("Manual", encoding="utf-8")
    os.link(source, tmp_path / "AGENTS.md")
    with pytest.raises(Conflict, match="hard-linked"):
        plan(tmp_path, "AGENTS.md", "New\n", True)


def test_linked_parent_rejected(tmp_path):
    target = tmp_path / "outside"
    target.mkdir()
    try:
        (tmp_path / ".github").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink privileges unavailable")
    with pytest.raises(Conflict, match="linked destination"):
        plan(tmp_path, ".github/copilot-instructions.md", "New\n", True)
