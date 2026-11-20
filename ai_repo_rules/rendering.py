"""Format adapters over a single set of shared rules."""

from collections.abc import Iterable

from .models import Project, Scan

OUTPUTS = {
    "codex": "AGENTS.md",
    "claude": "CLAUDE.md",
    "copilot": ".github/copilot-instructions.md",
}
TITLES = {
    "codex": "Agent instructions",
    "claude": "Claude Code instructions",
    "copilot": "GitHub Copilot instructions",
}
SAFETY_RULES = (
    "- Read the applicable instructions, README, configuration, and tests before editing.",
    "- Make focused changes and preserve existing behavior and manual instructions.",
    "- Never print, commit, or copy secrets or private tokens.",
    "- Review configured commands before running them; configuration is not trusted code.",
    "- Use the environment and tool versions specified by the project.",
    "- Run relevant checks when practical; report results and anything unverified.",
    "- Do not invent commands, dependencies, or successful test results.",
)
# (label in the generated file, Project attribute / observation field)
FIELDS = (
    ("Languages", "languages"),
    ("Frameworks", "frameworks"),
    ("Package managers", "managers"),
    ("Evidence", "evidence"),
)
SCOPE_LINE = "Run commands from this project directory."
COMMANDS_INTRO = "Configured check invocations (availability has not been verified):"
NO_COMMANDS = "No unambiguous check commands detected. Inspect project configuration."


def literal(value: str) -> str:
    # Keep repository-controlled names from injecting Markdown instructions.
    return "`" + "".join(c if c.isprintable() and c not in "`<>" else "?" for c in value) + "`"


def header_line(project: Project) -> str:
    return f"### {literal(project.path)}"


def field_line(label: str, values: Iterable[str]) -> str:
    ordered = sorted(values)
    return (
        f"- {label}: "
        + (", ".join(literal(v) for v in ordered) if ordered else "not detected")
        + "."
    )


def command_line(command: str, source: str) -> str:
    return f"- {literal(command)} — evidence: {literal(source)}."


def warning_line(warning: str) -> str:
    return f"- {literal(warning)}"


def render(scan: Scan, agent: str) -> str:
    lines = [
        f"# {TITLES[agent]}",
        "",
        "Review this locally generated draft before committing.",
        "Keep manually maintained instructions outside the generated section.",
        "",
        "## Safety and workflow",
        "",
        *SAFETY_RULES,
        "",
        "## Detected projects",
        "",
    ]
    for project in scan.projects:
        lines += [header_line(project), "", SCOPE_LINE, ""]
        for label, attribute in FIELDS:
            lines.append(field_line(label, getattr(project, attribute)))
        if project.commands:
            lines += ["", COMMANDS_INTRO, ""]
            lines += [command_line(cmd, source) for cmd, source in sorted(project.commands)]
        else:
            lines += ["", NO_COMMANDS]
        lines.append("")
    if scan.warnings:
        lines += ["## Detection warnings", ""]
        lines += [warning_line(warning) for warning in scan.warnings]
        lines.append("")
    return "\n".join(lines)
