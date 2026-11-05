# Codex repository instructions

## Language and scope
- Write code and documentation in English. Keep documentation concise.
- Do not create a `docs/` directory.
- Respect existing architecture and conventions. Keep each task small and focused.
- Read the repository README and any relevant configuration before changing code.

## Branches and pull requests
- `main` is stable; `develop` is the integration branch. Never commit directly to either.
- For ordinary work, branch from the latest `develop` using `feature/`, `fix/`, `refactor/`, `docs/`, `chore/`, `test/`, `ci/`, or `perf/` followed by a short kebab-case description.
- Use `hotfix/` from `main` only for urgent production fixes, with explicit permission.
- Git tags are reserved for releases (`vMAJOR.MINOR.PATCH`); task types use branch prefixes and PR labels.
- Prefer Conventional Commit-style PR titles (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`, `test:`, `ci:`, `perf:`). Link an Issue when available; Issues are optional.
- Run applicable lint, type checks, tests, and build before submitting. Explain any skipped or failing check.
- Push the task branch and open a PR to `develop` when the environment permits. If credentials or UI access prevent this, provide the branch, diff summary, and exact manual steps; never claim a PR was created.
- Keep PR summaries short: purpose, changes, checks, risks, and manual steps.
- Never approve, merge, close, or delete a task PR yourself. The human owner reviews and merges; GitHub deletes merged temporary branches.

## Releases (only when explicitly requested)
- Do not release, bump version, create a version tag, or publish automatically after ordinary task merges.
- Inspect merged PR labels since the previous release; propose the next SemVer version to the owner (breaking => major; feature => minor; fix/perf => patch). The owner decides the final version.
- Prepare a `chore/release-vX.Y.Z` branch from `develop`, update `CHANGELOG.md` following Keep a Changelog and relevant version metadata, and create/update `UPGRADING.md` only when manual migration is necessary. Do not create an empty upgrade file.
- Submit the release-preparation PR to `develop` for human review. After it is merged, propose a PR from `develop` to `main` titled `release: vX.Y.Z`.
- The owner merges the release PR using **Create a merge commit** (not squash), then creates and pushes an annotated `vX.Y.Z` tag on the resulting `main` commit. The tag triggers GitHub Actions packaging and publishing.
- Never merge or tag on the owner's behalf unless the owner explicitly asks and the environment allows it; the default process is manual.
- After any approved urgent hotfix merged into `main`, ensure it also reaches `develop` through a reviewed sync PR. Update changelog/version and tag using the same manual release controls.

## Quality and safety
- Never disable, skip, or weaken CI, branch rules, or security checks just to obtain a passing PR.
- Never place credentials or secrets in code, commits, logs, or documentation.
- Avoid unrelated refactoring and generated-file churn.
- Record user-visible changes in the next release's changelog, not by inventing a release during ordinary tasks.
