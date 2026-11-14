import json
from pathlib import Path

import pytest

from ai_repo_rules.detection import scan


def put(root: Path, name: str, content: str = "") -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.mark.parametrize(
    ("name", "language", "manager"),
    [
        ("requirements.txt", "Python", None),
        ("Cargo.toml", "Rust", "Cargo"),
        ("go.mod", "Go", "Go modules"),
        ("pom.xml", "Java", "Maven"),
        ("build.gradle.kts", "Java", "Gradle"),
        ("App.csproj", "C#", "NuGet"),
        ("composer.json", "PHP", "Composer"),
        ("Gemfile", "Ruby", "Bundler"),
    ],
)
def test_manifest_languages(tmp_path, name, language, manager):
    put(tmp_path, name, "{}" if name.endswith("json") else "")
    project = scan(tmp_path).projects[0]
    assert language in project.languages
    if manager:
        assert manager in project.managers
    assert project.commands == []


@pytest.mark.parametrize("manager", ["npm", "pnpm", "yarn", "bun"])
def test_js_frameworks_and_safe_commands(tmp_path, manager):
    put(
        tmp_path,
        "package.json",
        json.dumps(
            {
                "packageManager": f"{manager}@1.0",
                "dependencies": {"next": "1", "react": "1", "react-native": "1", "typescript": "1"},
                "scripts": {
                    "test": "SECRET=value runner",
                    "lint:fix": "lint",
                    "test;evil": "x",
                    "start": "server",
                },
            }
        ),
    )
    project = scan(tmp_path).projects[0]
    assert project.frameworks == {"React", "Next.js", "React Native"}
    assert project.languages == {"JavaScript", "TypeScript"}
    assert {c for c, _ in project.commands} == {f"{manager} run test", f"{manager} run lint:fix"}
    assert "SECRET" not in repr(project)


@pytest.mark.parametrize("locks", [[], ["yarn.lock", "pnpm-lock.yaml"]])
def test_ambiguous_manager_never_guesses(tmp_path, locks):
    put(tmp_path, "package.json", '{"scripts":{"test":"test"}}')
    for lock in locks:
        put(tmp_path, lock)
    result = scan(tmp_path)
    assert not result.projects[0].commands
    assert result.warnings


def test_monorepo_scopes_and_exclusions(tmp_path):
    put(tmp_path, "package.json", "{}")
    put(tmp_path, "apps/web/package.json", '{"dependencies":{"react":"1"}}')
    put(tmp_path, "apps/web/src/index.tsx")
    put(tmp_path, "services/api/go.mod", "module example.com/api")
    for ignored in ["node_modules", "vendor", ".git", "dist", ".venv", "secrets", "target"]:
        put(tmp_path, f"{ignored}/hidden/pyproject.toml", "bad toml")
    result = scan(tmp_path)
    assert [p.path for p in result.projects] == [".", "apps/web", "services/api"]
    assert "TypeScript" in result.projects[1].languages
    assert "TypeScript" not in result.projects[0].languages
    assert not result.warnings


def test_reads_only_allowlisted_configuration(tmp_path, monkeypatch):
    put(tmp_path, "wp-config.php", "SECRET")
    put(tmp_path, ".env", "SECRET")
    put(tmp_path, "source.py", "SECRET")
    put(tmp_path, "requirements.txt", "SECRET")

    def forbidden(*args, **kwargs):
        raise AssertionError("Source and secret contents must not be read")

    monkeypatch.setattr(Path, "open", forbidden)
    project = scan(tmp_path).projects[0]
    assert "WordPress" in project.frameworks
    assert "Python" in project.languages


def test_python_configuration(tmp_path):
    put(
        tmp_path,
        "pyproject.toml",
        """
[project]
dependencies = ["fastapi>=0.1"]
[tool.pytest.ini_options]
testpaths = ["tests"]
[tool.ruff]
line-length = 100
""",
    )
    project = scan(tmp_path).projects[0]
    assert project.frameworks == {"FastAPI"}
    assert {cmd for cmd, _ in project.commands} == {"python -m pytest", "ruff check ."}


def test_composer(tmp_path):
    put(
        tmp_path,
        "composer.json",
        '{"require":{"roots/wordpress":"*"},"scripts":{"test":"phpunit","lint":"phpcs"}}',
    )
    project = scan(tmp_path).projects[0]
    assert "WordPress" in project.frameworks
    assert ("composer run-script test", "composer.json") in project.commands


@pytest.mark.parametrize("content", ["{", "[]", '{"scripts":null,"dependencies":5}'])
def test_malformed_json_is_tolerated(tmp_path, content):
    put(tmp_path, "package.json", content)
    assert scan(tmp_path).projects


def test_oversized_config(tmp_path):
    put(tmp_path, "package.json", " " * 1_000_001)
    assert "oversized" in scan(tmp_path).warnings[0]


def test_invalid_toml_and_wrong_tool_types(tmp_path):
    put(tmp_path, "pyproject.toml", "invalid TOML")
    assert scan(tmp_path).warnings
    put(tmp_path, "pyproject.toml", '[tool]\npytest = "not configuration"')
    assert not scan(tmp_path).projects[0].commands


def test_scan_limits_warn(tmp_path, monkeypatch):
    put(tmp_path, "nested/deeper/go.mod")
    monkeypatch.setattr("ai_repo_rules.detection.MAX_DEPTH", 1)
    assert any("Depth limit" in warning for warning in scan(tmp_path).warnings)
    monkeypatch.setattr("ai_repo_rules.detection.MAX_FILES", 0)
    put(tmp_path, "source.py")
    assert any("File limit" in warning for warning in scan(tmp_path).warnings)


def test_windows_reparse_point_is_link(tmp_path, monkeypatch):
    import stat
    from types import SimpleNamespace

    from ai_repo_rules.detection import is_link

    monkeypatch.setattr(
        Path,
        "lstat",
        lambda self: SimpleNamespace(
            st_mode=stat.S_IFDIR, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT
        ),
    )
    assert is_link(tmp_path)


def test_case_insensitive_exclusions(tmp_path):
    put(tmp_path, "NODE_MODULES/package.json", "{}")
    assert len(scan(tmp_path).projects) == 1


def test_symlink_not_scanned(tmp_path):
    target = tmp_path / "excluded"
    target.mkdir()
    link = tmp_path / "linked"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink privileges unavailable")
    put(target, "go.mod")
    assert "linked" not in [p.path for p in scan(tmp_path).projects]
