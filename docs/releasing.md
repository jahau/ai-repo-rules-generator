# Release checklist

Releases are distributed as GitHub release assets (wheel and source archive).
The package is not published to a package index.

1. Bump `version` in `pyproject.toml` and `__version__` in
   `ai_repo_rules/__init__.py`, and move the `Unreleased` changelog entries under
   a dated version heading in `CHANGELOG.md`.
2. Merge the reviewed PR after the operating-system/Python CI matrix passes.
3. Build from a clean checkout of `main` with `python -m build` and test the wheel
   outside the checkout. CI also uploads both distributions for inspection.
4. Tag the merged commit `vX.Y.Z`, push the tag, and create the GitHub release
   with the wheel and source archive attached.
5. Publish to a package index only after confirming package ownership and
   credentials.
