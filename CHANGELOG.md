# Changelog

## 0.2.0 — release candidate

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
No package publication or release tag has been made by this change.

## 0.1.0

- Initial standalone Python prototype generating `AGENTS.md` from root manifests.
