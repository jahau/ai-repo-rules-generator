# AI Repo Rules Generator

Give your coding assistant instructions grounded in your repository—without
uploading code or replacing the rules your team already maintains.

**One local scan. Three assistant formats. Review every change before writing.**
AI Repo Rules Generator finds project boundaries, technologies, and configured
checks, then creates a conservative instruction draft. It has no runtime
dependencies, makes no API calls, and never executes project scripts.

## Install

Requires Python 3.11 or newer on Windows, Linux, or macOS. From a checkout:

```sh
git clone https://github.com/jahau/ai-repo-rules-generator.git
cd ai-repo-rules-generator
python -m pip install .
ai-repo-rules --version
```

Prebuilt wheels are attached to each
[GitHub release](https://github.com/jahau/ai-repo-rules-generator/releases); the
package is not published to a package index. You can also run directly without
installing:

```sh
python generate_rules.py /path/to/project
python -m ai_repo_rules /path/to/project
```

## Preview, generate, update

```sh
# Inspect the proposed contents; neither command writes files.
ai-repo-rules /path/to/project --agent all --dry-run
ai-repo-rules /path/to/project --agent all --diff

# Generate all three instruction files.
ai-repo-rules /path/to/project --agent all

# Preview updates while preserving manually maintained instructions.
ai-repo-rules /path/to/project --agent all --update --diff
ai-repo-rules /path/to/project --agent all --update
```

Quote paths containing spaces, including Windows paths such as
`ai-repo-rules "C:\Projects\My App" --diff`. The project defaults to the current
directory and the agent defaults to `codex`.

| Agent option | Output relative to the project root |
| --- | --- |
| `--agent codex` | `AGENTS.md` |
| `--agent claude` | `CLAUDE.md` |
| `--agent copilot` | `.github/copilot-instructions.md` |
| `--agent all` | All three files |

All adapters use the same evidence and workflow rules. Nested projects appear as
scoped sections with their working directories in each root instruction file;
the generator does not create separate instruction files in every package.

## Safe updates

By default, an existing destination is never modified: a file that is already up
to date is reported as unchanged, and any other existing file is a conflict.
`--update` appends a generated section to a manual-only file or refreshes an
existing, unedited generated section. Text outside the markers is preserved,
including Unicode, BOMs, and line endings. Repeated updates are idempotent.

Generated sections have SHA-256 checksums. Editing a generated section, deleting
one of its markers, or duplicating markers causes a conflict. Keep custom rules
outside the markers. To resolve a conflict, move your edits outside the section
and restore its original content from version control, or remove both markers
while retaining all text to treat the whole file as manual content on the next
update. Review the diff for duplicated guidance in that case.

All destinations are checked before any writes, and writes are all-or-nothing.
Updates are first staged as temporary files, then applied with atomic replacement;
new files use exclusive creation. If any write fails, completed writes are rolled
back and newly created directories are removed.
Symlinks, Windows reparse points, and hard-linked destinations are refused.
`--force` is accepted for compatibility but now means safe `--update`, with a
warning; there is no destructive overwrite option.

## Explain generated instructions

`--explain` shows which metadata observations produced each generated instruction,
with a confidence level and the project scope it applies to. It is strictly
read-only: it does not plan, read, or write instruction files, so it never
conflicts with existing files and leaves every byte untouched. It cannot be
combined with `--dry-run`, `--diff`, `--update`, or `--force`; run a normal
generation command when you want files changed.

```sh
ai-repo-rules /path/to/project --explain
ai-repo-rules /path/to/project --agent all --explain --explain-format json
```

Excerpt for [examples/monorepo](examples/monorepo):

```text
Scope `apps/web` -> ### `apps/web`
  Run commands from this project directory.
      `apps/web` [high]
        [high] `apps/web/package.json`: recognized manifest present
  - Languages: `JavaScript`, `TypeScript`.
      `JavaScript` [high]
        [high] `apps/web/package.json`: manifest parsed
      `TypeScript` [high]
        [high] `apps/web/package.json`: `devDependencies.typescript` declared
  ...
  - `pnpm run test` — evidence: `package.json`.
      `pnpm run test` [medium]
        [medium] `apps/web/package.json`: script name `scripts.test` matches a check pattern; `pnpm` is the only manager
```

Each indented instruction line is byte-identical to a line in the generated
section. Below it, each listed value shows its strongest confidence and every
supporting observation, using repository-relative paths:

| Confidence | Meaning |
| --- | --- |
| `high` | Declared in a parsed allowlisted manifest field, or implied by a recognized manifest or lockfile name |
| `medium` | Inferred from file extensions (with the directories counted) or from a script-name pattern |
| `low` | Filename-only heuristic that may be coincidental, such as `wp-config-sample.php` |

Lines with nothing detected say `no allowlisted observation`. When scripts are
omitted, the explanation names the cause, for example "the package manager is
ambiguous (npm, yarn); no invocation is guessed".
Template lines (title, safety rules, headings) are listed separately as not
derived from individual observations. Detection warnings are printed to stderr as
usual and repeated in the explanation. If scripts were omitted in a scope that
still has other commands, the omission is explained against its warning line.

Output is deterministic: identical repository metadata gives identical text or
JSON in any checkout location. JSON (`"format": "ai-repo-rules-explain/1"`) has
sorted keys and ASCII escaping, so it is suitable for diffs and CI checks. Text
mode escapes characters the console encoding cannot represent instead of failing.
Golden examples for a nested monorepo, unknown manifests, and ambiguous package
managers live in [tests/golden](tests/golden).

Explanation limitations:

- It explains what the scanner observed, not whether a command works or a
  framework is actually used. Confidence is a fixed rule per observation kind,
  not a statistical score.
- Unrecognized manifests (for example `deno.json`, `pubspec.yaml`, `Makefile`)
  are not read and never appear. Their directories do not become scopes, and
  source files there are attributed to the nearest recognized project.
- Lockfiles and `packageManager` apply only to their own directory. A workspace
  root's lockfile does not make a nested package's manager unambiguous.
- Files skipped by exclusions or scan limits are absent from explanations too.
  Check the warnings.
- Directory names, dependency keys, and script names can appear in the output;
  values are shown as sanitized code spans in text mode.

## Detection support

| Ecosystem | Evidence and scope |
| --- | --- |
| Python | `.py`, `pyproject.toml`, `requirements.txt`; Django, Flask, FastAPI from declared metadata; Poetry/uv/Pipenv evidence |
| JavaScript / TypeScript | Source extensions, `package.json`, TypeScript dependency; npm, pnpm, yarn, bun from lockfiles or `packageManager` |
| React / Next.js / React Native | Exact dependency names in `package.json` |
| PHP / WordPress | `.php`, Composer; WordPress Composer packages or `wp-config.php` / `wp-config-sample.php` filenames only |
| Go | `.go`, `go.mod`, Go modules |
| Rust | `.rs`, `Cargo.toml`, Cargo |
| Java | `.java`, `pom.xml`, Gradle manifests; Maven/Gradle |
| C# | `.cs`, `.csproj`, NuGet |
| Ruby (legacy support) | `.rb`, `Gemfile`, Bundler |

Every directory containing a supported manifest is a project boundary. Source
extensions belong to the nearest enclosing project. This works without Git and
finds nested projects even when they are not listed in a workspace manifest.

Check discovery supports test/lint/check/typecheck/format script names in
`package.json` and `composer.json`. Script bodies are never copied into output.
JavaScript scripts require an unambiguous package manager in the same directory.
Explicit pytest and Ruff configuration in `pyproject.toml` yields standard tool
invocations, labelled as configured but unverified. Tools need not be installed.
Other language manifests identify the stack but do **not** cause guessed test,
build, or lint commands to be emitted.

## Real terminal demo and sample output

This excerpt is from the reproducible CLI session in [docs/demo.txt](docs/demo.txt):

```text
$ python generate_rules.py project --agent all --dry-run
Detected 3 project(s).
Would Create: AGENTS.md
Would Create: CLAUDE.md
Would Create: .github/copilot-instructions.md
Preview only; no files written.
[exit 0]
```

Run `python scripts/demo.py` to capture the full session again, including unified
diffs, generation, an unchanged update, and an unchanged rerun without `--update`. It uses a
temporary copy of [examples/monorepo](examples/monorepo) and writes the transcript
and sample files under `docs/`.

Full generated samples:
[AGENTS.md](docs/samples/AGENTS.md), [CLAUDE.md](docs/samples/CLAUDE.md),
[Copilot instructions](docs/samples/copilot-instructions.md).

## Privacy and limitations

- The CLI has no network client, telemetry, or external model integration. Package
  installation can use the network; repository scanning and generation do not.
- Scanning reads only `package.json`, `composer.json`, and `pyproject.toml` content.
  Other evidence uses filenames/extensions only. It does not read `.env`, source
  code, lockfile contents, or WordPress configuration contents. Do not embed secrets
  in manifest keys or directory names; names can appear in generated evidence.
- Hidden directories and common dependencies, caches, build artifacts, Git metadata,
  and secret directories are excluded. See `EXCLUDED` in `detection.py` for the list.
  Gitignore rules and custom artifact directories are not interpreted. Only
  allowlisted configuration content is read even in other directories.
- Scan limits are 50,000 files, depth 30, and 1 MB per configuration file. Unreadable,
  oversized, or malformed configuration produces warnings where encountered.
- No dependency resolution, source analysis, shell parsing, CI command extraction,
  inherited workspace-manager inference, or arbitrary task-runner parsing occurs.
  Standalone WordPress plugins/themes without recognized metadata may appear as PHP.
- Manifest presence is evidence, not proof of a working build. Generated drafts can
  include fixture projects; review their relevance. Commands are never executed or
  claimed to have passed. This tool does not validate assistant behavior.
- UTF-8 instruction files are required. Manual instructions can contradict generated
  guidance; semantic conflict resolution remains a human review task.
- Failed writes are rolled back, but a crash or power loss during the brief apply
  phase can still leave a subset completed. Avoid concurrent edits during generation: snapshot
  checks detect ordinary changes, but there is no cross-process lock or protection
  against a malicious process changing filesystem paths during the write window.

## Troubleshooting and exit codes

| Exit | Meaning | Action |
| --- | --- | --- |
| `0` | Generated, unchanged, preview, or explanation completed | Review output; detection warnings may still need attention |
| `1` | `--explain` output pipe was closed early (for example `\| head`) | Expected when truncating output; rerun without the pipe for the full explanation |
| `2` | Invalid arguments or project path | Check `--help` and the directory |
| `3` | Existing file, edited block, or unsafe destination | Inspect the file; use `--update --diff` or resolve the reported conflict |
| `4` | Filesystem I/O failure | Check permissions and disk space; completed writes are rolled back; a rollback failure lists files to inspect |

Missing commands usually mean evidence is absent or the package manager is
ambiguous; `--explain` names the cause for each scope. Keep only the intended lockfile/manager declaration and rerun. The tool
does not add missing dependencies or configuration for you.

## Development and release

```sh
python -m pip install -e ".[dev]" build
python -m pytest -q
ruff check ai_repo_rules tests scripts generate_rules.py
ruff format --check ai_repo_rules tests scripts generate_rules.py
mypy ai_repo_rules
python -m build
```

The CI matrix covers Python 3.11–3.14 on Windows, Linux, and macOS, with wheel
installation and an out-of-checkout CLI smoke test. Tests cover detection,
previews, legacy invocation, conflict handling, manual-text preservation, unsafe
paths, offline execution, and golden `--explain` fixtures (refresh them after an
intentional change with `UPDATE_GOLDEN=1 python -m pytest tests/test_explain.py`). Symlink tests skip if the host cannot create links.

See [CHANGELOG.md](CHANGELOG.md) and the
[release checklist](docs/releasing.md). MIT licensed.
