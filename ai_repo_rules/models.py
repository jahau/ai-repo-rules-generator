"""Shared evidence model used by every output adapter."""

from dataclasses import dataclass, field

HIGH = "high"
MEDIUM = "medium"
LOW = "low"
CONFIDENCE_RANK = {HIGH: 3, MEDIUM: 2, LOW: 1}


@dataclass(frozen=True, order=True)
class Observation:
    """One piece of safe metadata and the generated value it supports.

    ``field`` is ``scope``, ``languages``, ``frameworks``, ``managers``, ``evidence``,
    ``commands`` or ``omissions``. ``source`` is a repository-relative path or glob;
    ``directories`` lists repository-relative directories for extension observations.
    """

    field: str
    value: str
    source: str
    detail: str
    confidence: str
    directories: tuple[str, ...] = ()


@dataclass
class Project:
    path: str
    languages: set[str] = field(default_factory=set)
    frameworks: set[str] = field(default_factory=set)
    managers: set[str] = field(default_factory=set)
    evidence: set[str] = field(default_factory=set)
    commands: list[tuple[str, str]] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)

    def observe(
        self,
        kind: str,
        value: str,
        source: str,
        detail: str,
        confidence: str,
        directories: tuple[str, ...] = (),
    ) -> None:
        """Record a generated value together with the observation that caused it."""
        if kind in {"languages", "frameworks", "managers", "evidence"}:
            getattr(self, kind).add(value)
        self.observations.append(Observation(kind, value, source, detail, confidence, directories))


@dataclass
class Scan:
    projects: list[Project]
    warnings: list[str] = field(default_factory=list)
