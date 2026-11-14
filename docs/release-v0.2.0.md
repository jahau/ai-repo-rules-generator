# v0.2.0 release preparation

The package metadata and CLI version are set to `0.2.0`. This change prepares the
release; it does not publish a package or create a release tag.

Before publishing:

1. Merge the reviewed PR after the operating-system/Python CI matrix passes.
2. Build from a clean checkout with `python -m build` and test the wheel outside
   the checkout. CI uploads both distributions for inspection.
3. Set the release date in `CHANGELOG.md`, tag the reviewed commit `v0.2.0`, and
   attach the wheel and source archive to the GitHub release.
4. Publish to a package index only after confirming package ownership and credentials.

Release highlights: three agent formats; nested-project detection; local-only
analysis; non-writing previews; safe, checksummed updates that preserve manual text.

Migration: Python 3.11+ is required. Existing `python generate_rules.py <project>`
usage still works. Use `--update` to append rules to an existing instruction file.
`--force` now preserves manual content and emits a deprecation warning.
