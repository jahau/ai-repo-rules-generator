"""Read-only explanations linking every generated instruction to the metadata behind it.

Explanations are built from the same scan and the same line helpers as ``render``, so
each explained instruction is byte-identical to a line in the generated section. They
contain only repository-relative paths, so output is reproducible across checkouts.
"""

from __future__ import annotations

import json
from typing import Any

from .detection import scripts_omitted
from .models import CONFIDENCE_RANK, Observation, Project, Scan
from .rendering import (
    COMMANDS_INTRO,
    FIELDS,
    NO_COMMANDS,
    OUTPUTS,
    SAFETY_RULES,
    SCOPE_LINE,
    TITLES,
    command_line,
    field_line,
    header_line,
    literal,
    warning_line,
)

FORMAT = "ai-repo-rules-explain/1"
CONFIDENCE = {
    "high": "declared in a parsed allowlisted manifest field, or implied by a recognized "
    "manifest or lockfile name",
    "medium": "inferred from file extensions or from a script-name pattern",
    "low": "filename-only heuristic that may be coincidental",
}
MAX_LISTED_DIRECTORIES = 5


def _observation(item: Observation) -> dict[str, Any]:
    data: dict[str, Any] = {
        "source": item.source,
        "detail": item.detail,
        "confidence": item.confidence,
    }
    if item.directories:
        data["directories"] = list(item.directories)
    return data


def _value(project: Project, kind: str, value: str) -> dict[str, Any]:
    basis = sorted(
        (o for o in project.observations if o.field == kind and o.value == value),
        key=lambda o: (-CONFIDENCE_RANK[o.confidence], o.source, o.detail),
    )
    return {
        "value": value,
        # A value is as trustworthy as its strongest supporting observation.
        "confidence": basis[0].confidence if basis else None,
        "observations": [_observation(o) for o in basis],
    }


def _project(project: Project) -> dict[str, Any]:
    instructions: list[dict[str, Any]] = [
        {
            "instruction": SCOPE_LINE,
            "field": "scope",
            "values": [_value(project, "scope", project.path)],
        }
    ]
    for label, attribute in FIELDS:
        values = sorted(getattr(project, attribute))
        instructions.append(
            {
                "instruction": field_line(label, values),
                "field": attribute,
                "values": [_value(project, attribute, v) for v in values],
            }
        )
    for command, source in sorted(project.commands):
        instructions.append(
            {
                "instruction": command_line(command, source),
                "field": "commands",
                "values": [_value(project, "commands", command)],
            }
        )
    omitted = sorted({o.value for o in project.observations if o.field == "omissions"})
    if not project.commands or omitted:
        # With other commands present, the omission surfaces only as a detection warning.
        line = NO_COMMANDS if not project.commands else warning_line(scripts_omitted(project.path))
        instructions.append(
            {
                "instruction": line,
                "field": "omissions",
                "values": [_value(project, "omissions", v) for v in omitted],
            }
        )
    return {"scope": project.path, "heading": header_line(project), "instructions": instructions}


def explain(scan: Scan, agents: list[str]) -> dict[str, Any]:
    """Return a deterministic, JSON-serializable explanation of ``render`` output."""
    template = [
        *(f"# {TITLES[agent]}" for agent in agents),
        "Review this locally generated draft before committing.",
        "Keep manually maintained instructions outside the generated section.",
        "## Safety and workflow",
        *SAFETY_RULES,
        "## Detected projects",
    ]
    if any(project.commands for project in scan.projects):
        template.append(COMMANDS_INTRO)
    if scan.warnings:
        template.append("## Detection warnings")
    return {
        "format": FORMAT,
        "read_only": True,
        "targets": [{"agent": agent, "path": OUTPUTS[agent]} for agent in agents],
        "template": template,
        "projects": [_project(project) for project in scan.projects],
        "warnings": [
            {"instruction": warning_line(w), "basis": "raised while scanning"}
            for w in scan.warnings
        ],
        "confidence_levels": CONFIDENCE,
    }


def to_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _where(directories: list[str]) -> str:
    if not directories:
        return ""
    shown = ", ".join(literal(d) for d in directories[:MAX_LISTED_DIRECTORIES])
    extra = len(directories) - MAX_LISTED_DIRECTORIES
    return f" in {shown}" + (f" and {extra} more director(ies)" if extra > 0 else "")


def to_text(data: dict[str, Any]) -> str:
    lines = [
        "ai-repo-rules explanation (read-only; no files were written)",
        "Targets: " + ", ".join(literal(t["path"]) for t in data["targets"]),
        "",
        "Template lines (not derived from individual observations; the last headings "
        "appear only when their section is generated):",
        *(f"  {line}" for line in data["template"]),
    ]
    for project in data["projects"]:
        lines += ["", f"Scope {literal(project['scope'])} -> {project['heading']}"]
        for item in project["instructions"]:
            lines.append(f"  {item['instruction']}")
            if not item["values"]:
                lines.append("      no allowlisted observation")
            for value in item["values"]:
                lines.append(f"      {literal(value['value'])} [{value['confidence']}]")
                for basis in value["observations"]:
                    lines.append(
                        f"        [{basis['confidence']}] {literal(basis['source'])}"
                        + _where(basis.get("directories", []))
                        + f": {basis['detail']}"
                    )
    if data["warnings"]:
        lines += ["", "Detection warnings (listed verbatim in the generated section):"]
        for item in data["warnings"]:
            lines += [f"  {item['instruction']}", f"      {item['basis']}"]
    lines += ["", "Confidence levels:"]
    lines += [f"  {level}: {meaning}" for level, meaning in data["confidence_levels"].items()]
    return "\n".join(lines) + "\n"
