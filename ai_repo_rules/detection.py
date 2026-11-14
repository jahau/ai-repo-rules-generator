"""Bounded local scanning. Only allowlisted configuration files are read."""

from __future__ import annotations

import json
import os
import re
import stat
import tomllib
from pathlib import Path
from typing import Any

from .models import Project, Scan

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


def _manifest(name: str) -> bool:
    return name in MANIFESTS or name.endswith(".csproj")


def _read(path: Path, root: Path, warnings: list[str]) -> str | None:
    try:
        if is_link(path) or not path.is_file():
            return None
        with path.open("rb") as stream:
            data = stream.read(MAX_CONFIG_BYTES + 1)
        if len(data) > MAX_CONFIG_BYTES:
            warnings.append(f"Skipped oversized configuration: {path.relative_to(root)}")
            return None
        return data.decode("utf-8-sig")
    except (OSError, UnicodeError):
        warnings.append(f"Could not read configuration: {path.relative_to(root)}")
        return None


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _scripts(data: dict[str, Any], prefix: str, source: str, project: Project) -> None:
    # Emit invocation names only, never script bodies (which may contain credentials).
    for name in sorted(_mapping(data.get("scripts"))):
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:_-]*", name):
            if re.search(r"(^|[:_-])(test|lint|check|typecheck|format)([:_-]|$)", name):
                project.commands.append((f"{prefix} {name}", source))


def _detect(directory: Path, names: set[str], root: Path, warnings: list[str]) -> Project:
    project = Project(directory.relative_to(root).as_posix())
    for name in sorted(names):
        suffix = Path(name).suffix
        if suffix in EXTENSIONS:
            project.languages.add(EXTENSIONS[suffix])
        if name in LOCKS:
            project.managers.add(LOCKS[name])
            project.evidence.add(name)
        if _manifest(name):
            project.evidence.add(name)
        if name in {"pyproject.toml", "requirements.txt", "Pipfile"}:
            project.languages.add("Python")
        if name == "Cargo.toml":
            project.languages.add("Rust")
            project.managers.add("Cargo")
        if name == "go.mod":
            project.languages.add("Go")
            project.managers.add("Go modules")
        if name in {"pom.xml", "build.gradle", "build.gradle.kts"}:
            project.languages.add("Java")
            project.managers.add("Maven" if name == "pom.xml" else "Gradle")
        if name.endswith(".csproj"):
            project.languages.add("C#")
            project.managers.add("NuGet")
        if name == "Gemfile":
            project.languages.add("Ruby")
            project.managers.add("Bundler")
        if name == "wp-config.php" or name == "wp-config-sample.php":
            project.languages.add("PHP")
            project.frameworks.add("WordPress")
            project.evidence.add(name + " (filename only)")
        if name not in {"package.json", "composer.json", "pyproject.toml"}:
            continue
        text = _read(directory / name, root, warnings)
        if text is None:
            continue
        try:
            data = _mapping(tomllib.loads(text) if name.endswith("toml") else json.loads(text))
        except (ValueError, RecursionError):
            warnings.append(f"Invalid configuration: {(directory / name).relative_to(root)}")
            continue
        if name == "package.json":
            project.languages.add("JavaScript")
            deps = _mapping(data.get("dependencies")) | _mapping(data.get("devDependencies"))
            for dependency, framework in {
                "react": "React",
                "next": "Next.js",
                "react-native": "React Native",
            }.items():
                if dependency in deps:
                    project.frameworks.add(framework)
            if "typescript" in deps:
                project.languages.add("TypeScript")
            explicit = str(data.get("packageManager", "")).split("@")[0]
            managers = {LOCKS[n] for n in names if n in LOCKS} & {"npm", "yarn", "pnpm", "bun"}
            if explicit in {"npm", "yarn", "pnpm", "bun"}:
                managers.add(explicit)
            project.managers.update(managers)
            if len(managers) == 1:
                _scripts(data, f"{next(iter(managers))} run", name, project)
            elif _mapping(data.get("scripts")):
                warnings.append(
                    f"{project.path}: package manager missing or ambiguous; scripts omitted"
                )
        elif name == "composer.json":
            project.languages.add("PHP")
            project.managers.add("Composer")
            deps = _mapping(data.get("require")) | _mapping(data.get("require-dev"))
            if any(d in deps for d in ("johnpbloch/wordpress", "roots/wordpress")):
                project.frameworks.add("WordPress")
            _scripts(data, "composer run-script", name, project)
        else:
            metadata = _mapping(data.get("project"))
            tool = _mapping(data.get("tool"))
            deps_list = metadata.get("dependencies", [])
            python_deps = (
                {re.split(r"[\s\[<>=!~;]", d.lower())[0] for d in deps_list if isinstance(d, str)}
                if isinstance(deps_list, list)
                else set()
            )
            python_deps.update(_mapping(_mapping(tool.get("poetry")).get("dependencies")))
            for dependency, framework in {
                "django": "Django",
                "flask": "Flask",
                "fastapi": "FastAPI",
            }.items():
                if dependency in python_deps:
                    project.frameworks.add(framework)
            if "poetry" in tool:
                project.managers.add("Poetry")
            if "uv" in tool:
                project.managers.add("uv")
            # These are configured tool invocations, never assumptions based on language.
            for key, command in {"pytest": "python -m pytest", "ruff": "ruff check ."}.items():
                if isinstance(tool.get(key), dict):
                    project.commands.append((command, f"{name} [tool.{key}]"))
    return project


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
                warnings.append(f"Depth limit reached: {directory.relative_to(root)}")
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
    for directory, names in directories.items():
        owner = directory
        while owner not in projects and owner != root:
            owner = owner.parent
        if owner in projects:
            for name in names:
                if Path(name).suffix in EXTENSIONS:
                    projects[owner].languages.add(EXTENSIONS[Path(name).suffix])
    return Scan(sorted(projects.values(), key=lambda p: p.path), warnings)
