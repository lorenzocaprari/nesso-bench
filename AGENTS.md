# AGENTS.md

Instructions for coding agents on nesso-bench. Human-facing rules are in
[CONTRIBUTING.md](CONTRIBUTING.md); follow them.

## Hard rules

- Commits a coding agent writes are authored and committed as Lorenzo Caprari
  <caprarilorenzo5@gmail.com>, with no `Co-authored-by`, `Signed-off-by`, or any other trailer.
- One commit per pull request. To collapse a branch after `main` moved, rebase onto
  `origin/main` first, then squash, and check `git diff --stat origin/main HEAD` lists only the
  files the pull request intends to change. Never `git reset --soft origin/main` a stale branch:
  that reverts everything that landed on `main` since the branch was cut.
- Do not merge, tag, push to `main`, force-push a shared branch, or change repository settings.
  Lorenzo merges.
- Run `scripts/lint`, `scripts/actionlint`, `scripts/zizmor`, and `scripts/test` before pushing.
- Nothing from private planning documents (plan ids, dates, targets, pricing) goes into this
  public repository, its pull requests, commits, or issues.
- Heavy benchmark workflows are `workflow_dispatch` or scheduled only, never `pull_request`.
