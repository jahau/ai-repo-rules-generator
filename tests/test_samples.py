from pathlib import Path

from ai_repo_rules.detection import scan
from ai_repo_rules.generation import block
from ai_repo_rules.rendering import OUTPUTS, render

ROOT = Path(__file__).resolve().parents[1]


def test_monorepo_samples_match_all_adapters():
    result = scan(ROOT / "examples" / "monorepo")
    assert len(result.projects) == 3
    assert not result.warnings
    for agent, output in OUTPUTS.items():
        sample = ROOT / "docs" / "samples" / Path(output).name
        assert sample.read_text(encoding="utf-8") == block(render(result, agent))


def test_polyglot_sample():
    result = scan(ROOT / "examples" / "polyglot")
    assert {p.path for p in result.projects} == {
        ".",
        "dotnet",
        "go",
        "java",
        "mobile",
        "rust",
        "wordpress",
    }
    assert not result.warnings
    assert set.union(*(p.languages for p in result.projects)) == {
        "C#",
        "Go",
        "Java",
        "JavaScript",
        "Rust",
        "PHP",
    }
    assert set.union(*(p.frameworks for p in result.projects)) == {
        "React",
        "React Native",
        "WordPress",
    }
