# AI Repo Rules Generator

A small, dependency-free CLI that detects a repository's technology stack and generates a **reviewable** `AGENTS.md` draft. It does not overwrite existing instructions unless `--force` is supplied.

## Usage

```bash
python generate_rules.py /path/to/project
python generate_rules.py /path/to/project --force
```

Review the generated instructions before committing them. Do not include secrets in prompts or generated rules.

## Roadmap
- `CLAUDE.md` and `.github/copilot-instructions.md` templates
- Existing-instruction merging without duplicate rules
- Better monorepo detection and configurable project policies
- Tests, examples and CLI packaging

MIT License. Contributions welcome.
