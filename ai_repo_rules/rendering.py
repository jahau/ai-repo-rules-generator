"""Format adapters over a single set of shared rules."""

from .models import Scan

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


def literal(value: str) -> str:
    # Keep repository-controlled names from injecting Markdown instructions.
    return "`" + "".join(c if c.isprintable() and c not in "`<>" else "?" for c in value) + "`"


def render(scan: Scan, agent: str) -> str:
    lines = [
        f"# {TITLES[agent]}",
        "",
        "Review this locally generated draft before committing.",
        "Keep manually maintained instructions outside the generated section.",
        "",
        "## Safety and workflow",
        "",
        "- Read the applicable instructions, README, configuration, and tests before editing.",
        "- Make focused changes and preserve existing behavior and manual instructions.",
        "- Never print, commit, or copy secrets or private tokens.",
        "- Review configured commands before running them; configuration is not trusted code.",
        "- Use the environment and tool versions specified by the project.",
        "- Run relevant checks when practical; report results and anything unverified.",
        "- Do not invent commands, dependencies, or successful test results.",
        "",
        "## Detected projects",
        "",
    ]
    for project in scan.projects:
        lines += [
            f"### {literal(project.path)}",
            "",
            "Run commands from this project directory.",
            "",
        ]
        for label, values in (
            ("Languages", project.languages),
            ("Frameworks", project.frameworks),
            ("Package managers", project.managers),
            ("Evidence", project.evidence),
        ):
            lines.append(
                f"- {label}: "
                + (", ".join(literal(v) for v in sorted(values)) if values else "not detected")
                + "."
            )
        if project.commands:
            lines += ["", "Configured check invocations (availability has not been verified):", ""]
            lines += [
                f"- {literal(cmd)} — evidence: {literal(source)}."
                for cmd, source in sorted(project.commands)
            ]
        else:
            lines += ["", "No unambiguous check commands detected. Inspect project configuration."]
        lines.append("")
    if scan.warnings:
        lines += ["## Detection warnings", ""]
        lines += [f"- {literal(warning)}" for warning in scan.warnings]
        lines.append("")
    return "\n".join(lines)
