"""Command-line interface. No network calls or project commands are executed."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .detection import scan
from .explain import explain, to_json, to_text
from .generation import Conflict, plan, write_changes
from .rendering import OUTPUTS, render


def _emit(text: str) -> int:
    """Print read-only output on any console encoding; a closed pipe is not an I/O failure."""
    stream = sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        # Non-UTF-8 consoles (e.g. redirected output on Windows) get escapes, not a crash.
        stream.write(text.encode(encoding, "backslashreplace").decode(encoding))
        stream.flush()
    except BrokenPipeError:
        # The reader closed early (e.g. `| head`); silence the flush at interpreter exit.
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), stream.fileno())
        except (OSError, ValueError):
            pass
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", default=".", type=Path)
    parser.add_argument("--agent", choices=[*OUTPUTS, "all"], default="codex")
    parser.add_argument("--dry-run", action="store_true", help="preview actions without writing")
    parser.add_argument("--diff", action="store_true", help="show unified diffs without writing")
    parser.add_argument(
        "--update", action="store_true", help="safely refresh or append managed rules"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="deprecated alias for --update; never discards manual content",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="show which metadata observations produced each generated instruction; "
        "read-only: never plans, reads, or writes instruction files",
    )
    parser.add_argument(
        "--explain-format",
        choices=["text", "json"],
        help="explanation output format (default: text); requires --explain",
    )
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    if args.explain_format and not args.explain:
        parser.error("--explain-format requires --explain")
    if args.explain and (args.dry_run or args.diff or args.update or args.force):
        parser.error("--explain cannot be combined with --dry-run, --diff, --update or --force")
    root = args.project.resolve()
    if not root.is_dir():
        print("Error: project directory not found.", file=sys.stderr)
        return 2
    if args.force:
        print("Warning: --force is deprecated; using safe --update behavior.", file=sys.stderr)
    try:
        result = scan(root)
        for warning in result.warnings:
            print(f"Warning: {warning}", file=sys.stderr)
        agents = list(OUTPUTS) if args.agent == "all" else [args.agent]
        if args.explain:
            data = explain(result, agents)
            return _emit(to_json(data) if args.explain_format == "json" else to_text(data))
        changes = [
            plan(root, OUTPUTS[agent], render(result, agent), args.update or args.force)
            for agent in agents
        ]
        preview = args.dry_run or args.diff
        if not preview:
            write_changes(root, changes)
        print(f"Detected {len(result.projects)} project(s).")
        for change in changes:
            action = (
                "Unchanged"
                if not change.changed
                else ("Create" if change.before is None else "Update")
            )
            print(
                f"{'Would ' if preview and change.changed else ''}{action}: "
                f"{change.path.relative_to(root).as_posix()}"
            )
            if args.diff and change.changed:
                print(change.diff(root), end="")
        if preview:
            print("Preview only; no files written.")
        return 0
    except Conflict as exc:
        print(f"Conflict: {exc}", file=sys.stderr)
        return 3
    except OSError as exc:
        print(f"I/O error: {exc}", file=sys.stderr)
        return 4
