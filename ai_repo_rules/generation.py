"""Plan all changes before writing; protect manual text and edited generated blocks."""

from __future__ import annotations

import difflib
import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .detection import is_link

PREFIX = "<!-- ai-repo-rules:begin"
END = "<!-- ai-repo-rules:end -->"
START_RE = re.compile(r"<!-- ai-repo-rules:begin sha256=([a-f0-9]{64}) -->\n")


class Conflict(Exception):
    """A destination needs manual resolution before any files can be written."""


@dataclass
class Change:
    path: Path
    before: bytes | None
    after: bytes

    @property
    def changed(self) -> bool:
        return self.before != self.after

    def diff(self, root: Path) -> str:
        return "".join(
            difflib.unified_diff(
                (self.before or b"").decode("utf-8").splitlines(keepends=True),
                self.after.decode("utf-8").splitlines(keepends=True),
                fromfile=f"a/{self.path.relative_to(root).as_posix()}",
                tofile=f"b/{self.path.relative_to(root).as_posix()}",
            )
        )


def digest(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def block(body: str) -> str:
    return f"{PREFIX} sha256={digest(body)} -->\n{body}{END}\n"


def safe_destination(root: Path, path: Path) -> None:
    for part in (path, *path.parents):
        if part == root:
            break
        if is_link(part):
            raise Conflict(f"Refusing linked destination: {path.relative_to(root)}")
    if path.exists() and not path.is_file():
        raise Conflict(f"Destination is not a regular file: {path.relative_to(root)}")
    if path.exists() and path.stat().st_nlink > 1:
        raise Conflict(f"Refusing hard-linked destination: {path.relative_to(root)}")


def plan(root: Path, relative: str, body: str, update: bool) -> Change:
    path = root / relative
    safe_destination(root, path)
    before = path.read_bytes() if path.exists() else None
    generated = block(body)
    if before is None:
        return Change(path, None, generated.encode("utf-8"))
    if not update:
        raise Conflict(f"{relative} already exists; use --update to preserve manual instructions")
    try:
        original = before.decode("utf-8")
    except UnicodeError as exc:
        raise Conflict(f"{relative} is not UTF-8; convert it manually before updating") from exc
    # Normalize only for validation. Preserve all surrounding bytes, including CRLF and BOM.
    normalized = original.replace("\r\n", "\n")
    if PREFIX not in normalized and END not in normalized:
        newline = "\r\n" if "\r\n" in original else "\n"
        separator = (
            ""
            if not original or original.endswith(newline * 2)
            else (newline if original.endswith(newline) else newline * 2)
        )
        return Change(
            path, before, (original + separator + generated.replace("\n", newline)).encode("utf-8")
        )
    matches = list(START_RE.finditer(normalized))
    if len(matches) != 1 or normalized.count(PREFIX) != 1 or normalized.count(END) != 1:
        raise Conflict(f"{relative}: malformed or duplicate generated markers; resolve manually")
    match = matches[0]
    end = normalized.index(END)
    if end < match.end() or digest(normalized[match.end() : end]) != match.group(1):
        raise Conflict(
            f"{relative}: generated section was edited; move manual edits outside "
            "the markers and restore the section before updating"
        )
    start_raw = original.index(PREFIX)
    body_start = original.index("\n", start_raw) + 1
    end_raw = original.index(END) + len(END)
    newline = "\r\n" if original[body_start - 2 : body_start] == "\r\n" else "\n"
    replacement = generated.rstrip("\n").replace("\n", newline)
    return Change(
        path, before, (original[:start_raw] + replacement + original[end_raw:]).encode("utf-8")
    )


def write_changes(root: Path, changes: list[Change]) -> None:
    # Validate the complete plan again before any mutation.
    for change in changes:
        safe_destination(root, change.path)
        current = change.path.read_bytes() if change.path.exists() else None
        if current != change.before:
            raise Conflict(f"{change.path.relative_to(root)} changed since planning; retry")
    for change in changes:
        if not change.changed:
            continue
        change.path.parent.mkdir(parents=True, exist_ok=True)
        safe_destination(root, change.path)
        if change.before is None:
            # Exclusive creation never clobbers a concurrently created destination.
            with change.path.open("xb") as stream:
                stream.write(change.after)
        else:
            fd, temporary = tempfile.mkstemp(prefix=".ai-repo-rules-", dir=change.path.parent)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(change.after)
                os.chmod(temporary, change.path.stat().st_mode)
                if change.path.read_bytes() != change.before:
                    raise Conflict(f"{change.path.name} changed during generation; retry")
                os.replace(temporary, change.path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
