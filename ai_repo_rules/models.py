"""Shared evidence model used by every output adapter."""

from dataclasses import dataclass, field


@dataclass
class Project:
    path: str
    languages: set[str] = field(default_factory=set)
    frameworks: set[str] = field(default_factory=set)
    managers: set[str] = field(default_factory=set)
    evidence: set[str] = field(default_factory=set)
    commands: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Scan:
    projects: list[Project]
    warnings: list[str] = field(default_factory=list)
