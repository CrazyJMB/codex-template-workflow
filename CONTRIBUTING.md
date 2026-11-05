# Contributing

1. Branch from `develop` (`feature/`, `fix/`, `refactor/`, `docs/`, `chore/`, `test/`, `ci/`, or `perf/`).
2. Make one focused change. Run `python scripts/check-template.py` and `bash scripts/ci.sh`; template regression tests belong in `tests/template/`.
3. Open a PR to `develop` with a conventional title and a linked Issue when available.
4. Wait for passing checks and manual owner review. The owner chooses **Squash and merge**.
5. Do not push to `main` or `develop` directly. GitHub deletes merged temporary branches; keep permanent branches.

Use kebab-case task names. Mark breaking changes with `!` in the title or the
`breaking` label. The policy job applies the matching type label and validates it
in the same run. Template setup requirements and commands are in `WORKFLOW.md`.

Releases require an explicit owner request, a reviewed release-preparation PR into `develop`, and a reviewed `develop` → `main` PR. See `WORKFLOW.md`.
