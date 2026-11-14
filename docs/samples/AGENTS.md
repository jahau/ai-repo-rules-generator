<!-- ai-repo-rules:begin sha256=662c6ece7f54581f90d2b886e99acd9ab97cefb9b89e050c3b87e097ac15ed4c -->
# Agent instructions

Review this locally generated draft before committing.
Keep manually maintained instructions outside the generated section.

## Safety and workflow

- Read the applicable instructions, README, configuration, and tests before editing.
- Make focused changes and preserve existing behavior and manual instructions.
- Never print, commit, or copy secrets or private tokens.
- Review configured commands before running them; configuration is not trusted code.
- Use the environment and tool versions specified by the project.
- Run relevant checks when practical; report results and anything unverified.
- Do not invent commands, dependencies, or successful test results.

## Detected projects

### `.`

Run commands from this project directory.

- Languages: `JavaScript`.
- Frameworks: not detected.
- Package managers: `pnpm`.
- Evidence: `package.json`.

No unambiguous check commands detected. Inspect project configuration.

### `apps/web`

Run commands from this project directory.

- Languages: `JavaScript`, `TypeScript`.
- Frameworks: `Next.js`, `React`.
- Package managers: `pnpm`.
- Evidence: `package.json`.

Configured check invocations (availability has not been verified):

- `pnpm run lint` — evidence: `package.json`.
- `pnpm run test` — evidence: `package.json`.

### `services/api`

Run commands from this project directory.

- Languages: `Python`.
- Frameworks: `FastAPI`.
- Package managers: not detected.
- Evidence: `pyproject.toml`.

Configured check invocations (availability has not been verified):

- `python -m pytest` — evidence: `pyproject.toml [tool.pytest]`.
<!-- ai-repo-rules:end -->
