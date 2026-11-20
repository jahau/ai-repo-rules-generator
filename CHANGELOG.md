# Changelog

## Unreleased

- Add read-only `--explain` (with `--explain-format text|json`). It shows the safe
  metadata observations behind every generated instruction, with confidence and
  project scope. It never plans, reads, or writes instruction files and rejects
  `--dry-run`, `--diff`, `--update`, and `--force`.
- Add fixture and golden tests for nested monorepos, unknown manifests, and
  ambiguous package managers. Generated output is unchanged.
- Detection warnings now use `/` path separators on every platform, so warnings
  in generated sections and explanations match across Windows and POSIX.

## 0.2.1 — 2026-11-14

- Rerunning without `--update` on an up-to-date file now reports `Unchanged` and
  exits 0 instead of a conflict; existing files are still never modified.
- Multi-file writes are all-or-nothing: updates are staged first, and any failure
  rolls back completed writes and removes newly created directories.

## 0.2.0 — 2026-11-14

- Add Codex, Claude Code, and GitHub Copilot output adapters with shared rules.
- Detect nested projects, source languages, supported frameworks, package managers,
  and configured check invocations from local evidence.
- Add non-writing `--dry-run` and `--diff` previews and checksummed `--update` sections.
- Preserve manual instructions, reject edited generated blocks, and preflight all
  requested destinations before writing.
- Exclude hidden directories, dependencies, build output, links, and Git metadata.
- Package the dependency-free CLI as `ai-repo-rules`; retain `generate_rules.py`.
- Add pytest coverage, typed modules, cross-platform CI, fixtures, generated samples,
  and a reproducible terminal demo.

Compatibility: Python 3.11+ is now required. `--force` remains accepted as a
deprecated alias for safe `--update`; it no longer deletes manual instructions.

## 0.1.0

- Initial standalone Python prototype generating `AGENTS.md` from root manifests.
