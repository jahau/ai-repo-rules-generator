#!/usr/bin/env python3
"""Generate a conservative, reviewable AGENTS.md draft from local project files."""
from pathlib import Path
import argparse

TECH = {
    'package.json': ('JavaScript/TypeScript', 'Run the repository-defined scripts; do not assume npm over pnpm or yarn.'),
    'pyproject.toml': ('Python', 'Use the project environment and configured lint/test tools.'),
    'requirements.txt': ('Python', 'Inspect requirements and prefer the existing virtual environment.'),
    'Cargo.toml': ('Rust', 'Use cargo fmt, cargo clippy and cargo test when available.'),
    'go.mod': ('Go', 'Use gofmt and go test ./... when appropriate.'),
    'composer.json': ('PHP', 'Respect Composer versions and PHP compatibility.'),
    'Gemfile': ('Ruby', 'Use Bundler and the configured test runner.'),
    'pom.xml': ('Java', 'Respect the project JDK and Maven build profile.'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', nargs='?', default='.', type=Path)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    folder = args.project.resolve()
    if not folder.is_dir(): raise SystemExit('Project directory not found.')
    found = [v for key, v in TECH.items() if (folder / key).exists()]
    destination = folder / 'AGENTS.md'
    if destination.exists() and not args.force:
        raise SystemExit('AGENTS.md already exists; refusing to overwrite. Use --force after review.')
    lines = ['# Agent instructions', '', 'Review this generated draft before committing.', '', '## Safety and workflow', '',
             '- Make minimal, focused changes and preserve existing behavior.',
             '- Read README, build configuration and tests before editing.',
             '- Never print, commit or copy secrets and private tokens.',
             '- Run relevant tests and lint commands when practical.',
             '- State what was tested and what remains unverified.', '', '## Detected stack', '']
    if found:
        for stack, guidance in dict.fromkeys(found): lines += [f'- **{stack}:** {guidance}']
    else: lines += ['- Unknown. Inspect project files and do not assume the technology stack.']
    destination.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('Created:', destination)


if __name__ == '__main__': main()
