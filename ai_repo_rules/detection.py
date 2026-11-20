"""Bounded local scanning. Only allowlisted configuration files are read."""

from __future__ import annotations

import json
import os
import re
import stat
import tomllib
from pathlib import Path
from typing import Any

from .models import HIGH, LOW, MEDIUM, Project, Scan

EXCLUDED = {
    "node_modules",
    "vendor",
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "dist",
    "build",
    "target",
    "bin",
    "obj",
    "coverage",
    ".next",
    ".nuxt",
    ".cache",
    ".uv-cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".idea",
    ".vscode",
    ".aws",
    ".ssh",
    "secrets",
    ".secrets",
    "Pods",
    ".gradle",
    ".yarn",
}
MANIFESTS = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "composer.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "Gemfile",
}
LOCKS = {
    "package-lock.json": "npm",
    "npm-shrinkwrap.json": "npm",
    "yarn.lock": "yarn",
    "pnpm-lock.yaml": "pnpm",
    "bun.lock": "bun",
    "bun.lockb": "bun",
    "poetry.lock": "Poetry",
    "uv.lock": "uv",
    "Pipfile.lock": "Pipenv",
    "Cargo.lock": "Cargo",
    "composer.lock": "Composer",
    "go.sum": "Go modules",
}
EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".php": "PHP",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".cs": "C#",
    ".rb": "Ruby",
}
# Filenames that imply a language and/or package manager without being read.
FILENAME_IMPLIES: dict[str, tuple[str | None, str | None]] = {
    "pyproject.toml": ("Python", None),
    "requirements.txt": ("Python", None),
    "Pipfile": ("Python", None),
    "Cargo.toml": ("Rust", "Cargo"),
    "go.mod": ("Go", "Go modules"),
    "pom.xml": ("Java", "Maven"),
    "build.gradle": ("Java", "Gradle"),
    "build.gradle.kts": ("Java", "Gradle"),
    "Gemfile": ("Ruby", "Bundler"),
}
JS_MANAGERS = {"npm", "yarn", "pnpm", "bun"}
MAX_CONFIG_BYTES = 1_000_000
MAX_FILES = 50_000
MAX_DEPTH = 30
EXCLUDED_CASEFOLD = {name.casefold() for name in EXCLUDED}


def is_link(path: Path) -> bool:
    """Also exclude Windows junctions, which can escape the repository."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def scripts_omitted(scope: str) -> str:
    """Warning text for package.json scripts dropped because no unique manager exists."""
    return f"{scope}: package manager missing or ambiguous; scripts omitted"


def _manifest(name: str) -> bool:
    return name in MANIFESTS or name.endswith(".csproj")


def _read(path: Path, root: Path, warnings: list[str]) -> str | None:
    try:
        if is_link(path) or not path.is_file():
            return None
        with path.open("rb") as stream:
            data = stream.read(MAX_CONFIG_BYTES + 1)
        if len(data) > MAX_CONFIG_BYTES:
            warnings.append(f"Skipped oversized configuration: {path.relative_to(root).as_posix()}")
            return None
        return data.decode("utf-8-sig")
    except (OSError, UnicodeError):
        warnings.append(f"Could not read configuration: {path.relative_to(root).as_posix()}")
        return None


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _source(project: Project, name: str) -> str:
    """Repository-relative path of a file inside ``project``."""
    return name if project.path == "." else f"{project.path}/{name}"


def _declared(data: dict[str, Any], keys: tuple[str, ...], dependency: str) -> str:
    found = [f"`{key}.{dependency}`" for key in keys if dependency in _mapping(data.get(key))]
    return ", ".join(found) + " declared"


def _scripts(data: dict[str, Any], prefix: str, source: str, project: Project, basis: str) -> None:
    # Emit invocation names only, never script bodies (which may contain credentials).
    for name in sorted(_mapping(data.get("scripts"))):
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:_-]*", name):
            if re.search(r"(^|[:_-])(test|lint|check|typecheck|format)([:_-]|$)", name):
                command = f"{prefix} {name}"
                project.commands.append((command, source))
                project.observe(
                    "commands",
                    command,
                    _source(project, source),
                    f"script name `scripts.{name}` matches a check pattern; {basis}",
                    MEDIUM,
                )


def _detect(directory: Path, names: set[str], root: Path, warnings: list[str]) -> Project:
    project = Project(directory.relative_to(root).as_posix())
    if not any(_manifest(n) for n in names):
        project.observe("scope", project.path, ".", "repository root is always a scope", HIGH)
    for name in sorted(names):
        source = _source(project, name)
        if name in LOCKS:
            project.observe("managers", LOCKS[name], source, "lockfile present", HIGH)
            project.observe("evidence", name, source, "lockfile present", HIGH)
        if _manifest(name):
            project.observe("scope", project.path, source, "recognized manifest present", HIGH)
            project.observe("evidence", name, source, "recognized manifest present", HIGH)
        language, manager = FILENAME_IMPLIES.get(name, (None, None))
        if language:
            project.observe("languages", language, source, "manifest filename", HIGH)
        if manager:
            project.observe("managers", manager, source, "manifest filename", HIGH)
        if name.endswith(".csproj"):
            project.observe("languages", "C#", source, "`.csproj` manifest filename", HIGH)
            project.observe("managers", "NuGet", source, "`.csproj` manifest filename", HIGH)
        if name == "wp-config.php" or name == "wp-config-sample.php":
            detail = "filename only; contents are never read"
            project.observe("languages", "PHP", source, detail, LOW)
            project.observe("frameworks", "WordPress", source, detail, LOW)
            project.observe("evidence", name + " (filename only)", source, detail, LOW)
        if name not in {"package.json", "composer.json", "pyproject.toml"}:
            continue
        text = _read(directory / name, root, warnings)
        if text is None:
            continue
        try:
            data = _mapping(tomllib.loads(text) if name.endswith("toml") else json.loads(text))
        except (ValueError, RecursionError):
            warnings.append(
                f"Invalid configuration: {(directory / name).relative_to(root).as_posix()}"
            )
            continue
        if name == "package.json":
            _package_json(data, names, source, project, warnings)
        elif name == "composer.json":
            project.observe("languages", "PHP", source, "manifest parsed", HIGH)
            project.observe("managers", "Composer", source, "manifest parsed", HIGH)
            keys = ("require", "require-dev")
            deps = _mapping(data.get("require")) | _mapping(data.get("require-dev"))
            for dependency in ("johnpbloch/wordpress", "roots/wordpress"):
                if dependency in deps:
                    detail = _declared(data, keys, dependency)
                    project.observe("frameworks", "WordPress", source, detail, HIGH)
            _scripts(data, "composer run-script", name, project, "runner is Composer")
        else:
            _pyproject(data, name, source, project)
    return project


def _package_json(
    data: dict[str, Any], names: set[str], source: str, project: Project, warnings: list[str]
) -> None:
    project.observe("languages", "JavaScript", source, "manifest parsed", HIGH)
    keys = ("dependencies", "devDependencies")
    deps = _mapping(data.get("dependencies")) | _mapping(data.get("devDependencies"))
    for dependency, framework in {
        "react": "React",
        "next": "Next.js",
        "react-native": "React Native",
    }.items():
        if dependency in deps:
            project.observe(
                "frameworks", framework, source, _declared(data, keys, dependency), HIGH
            )
    if "typescript" in deps:
        detail = _declared(data, keys, "typescript")
        project.observe("languages", "TypeScript", source, detail, HIGH)
    explicit = str(data.get("packageManager", "")).split("@")[0]
    managers = {LOCKS[n] for n in names if n in LOCKS} & JS_MANAGERS
    if explicit in JS_MANAGERS:
        managers.add(explicit)
        project.observe("managers", explicit, source, "`packageManager` field", HIGH)
    if len(managers) == 1:
        manager = next(iter(managers))
        _scripts(
            data, f"{manager} run", "package.json", project, f"`{manager}` is the only manager"
        )
    elif _mapping(data.get("scripts")):
        warnings.append(scripts_omitted(project.path))
        problem = f"ambiguous ({', '.join(sorted(managers))})" if managers else "missing"
        project.observe(
            "omissions",
            "package.json scripts",
            source,
            f"`scripts` declared but the package manager is {problem}; no invocation is guessed",
            HIGH,
        )


def _pyproject(data: dict[str, Any], name: str, source: str, project: Project) -> None:
    metadata = _mapping(data.get("project"))
    tool = _mapping(data.get("tool"))
    deps_list = metadata.get("dependencies", [])
    declared = (
        {re.split(r"[\s\[<>=!~;]", d.lower())[0] for d in deps_list if isinstance(d, str)}
        if isinstance(deps_list, list)
        else set()
    )
    poetry = _mapping(_mapping(tool.get("poetry")).get("dependencies"))
    for dependency, framework in {
        "django": "Django",
        "flask": "Flask",
        "fastapi": "FastAPI",
    }.items():
        if dependency in declared:
            detail = f"`project.dependencies` lists `{dependency}`"
            project.observe("frameworks", framework, source, detail, HIGH)
        if dependency in poetry:
            detail = f"`tool.poetry.dependencies.{dependency}` declared"
            project.observe("frameworks", framework, source, detail, HIGH)
    if "poetry" in tool:
        project.observe("managers", "Poetry", source, "`[tool.poetry]` table", HIGH)
    if "uv" in tool:
        project.observe("managers", "uv", source, "`[tool.uv]` table", HIGH)
    # These are configured tool invocations, never assumptions based on language.
    for key, command in {"pytest": "python -m pytest", "ruff": "ruff check ."}.items():
        if isinstance(tool.get(key), dict):
            project.commands.append((command, f"{name} [tool.{key}]"))
            project.observe("commands", command, source, f"`[tool.{key}]` table configured", HIGH)


def scan(root: Path) -> Scan:
    """Assign source extensions to the nearest manifest, preserving nested project scope."""
    warnings: list[str] = []
    directories: dict[Path, set[str]] = {}
    count = 0

    def walk_error(error: OSError) -> None:
        warnings.append("Could not enumerate a directory; detection is incomplete")

    for current, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        directory = Path(current)
        dirs[:] = sorted(
            d
            for d in dirs
            if d.casefold() not in EXCLUDED_CASEFOLD
            and not d.startswith(".")
            and not is_link(directory / d)
        )
        if len(directory.relative_to(root).parts) >= MAX_DEPTH:
            if dirs:
                warnings.append(f"Depth limit reached: {directory.relative_to(root).as_posix()}")
            dirs[:] = []
        names = {f for f in files if not is_link(directory / f)}
        count += len(names)
        if count > MAX_FILES:
            warnings.append("File limit reached; detection is incomplete")
            break
        directories[directory] = names
    projects: dict[Path, Project] = {}
    for directory, names in directories.items():
        if directory == root or any(_manifest(n) for n in names):
            projects[directory] = _detect(directory, names, root, warnings)
    # Source files are attributed by extension (never contents) to the nearest project.
    extensions: dict[tuple[Path, str], list[str]] = {}
    for directory, names in directories.items():
        owner = directory
        while owner not in projects and owner != root:
            owner = owner.parent
        if owner in projects:
            relative = directory.relative_to(root).as_posix()
            for name in names:
                suffix = Path(name).suffix
                if suffix in EXTENSIONS:
                    extensions.setdefault((owner, suffix), []).append(relative)
    for (owner, suffix), found in sorted(extensions.items()):
        projects[owner].observe(
            "languages",
            EXTENSIONS[suffix],
            f"*{suffix}",
            f"{len(found)} file(s) with this extension; nearest enclosing project",
            MEDIUM,
            tuple(sorted(set(found))),
        )
    return Scan(sorted(projects.values(), key=lambda p: p.path), warnings)
