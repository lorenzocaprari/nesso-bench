# Contributing

- **One commit per pull request.** Pull requests are squash-merged; the title becomes the commit
  on `main` and must be a conventional commit: `type(scope): subject`, with type one of `feat`,
  `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
- **Before pushing**, run `bash scripts/lint`, `bash scripts/actionlint`, `bash scripts/zizmor`,
  and `bash scripts/test`.
- **GitHub Actions** are pinned by full commit SHA with a trailing `# vX.Y.Z` comment.
  Jobs start with Harden-Runner in audit mode and use least-privilege `permissions`.
- **Pin everything a benchmark downloads.** A dataset needs a checksum, a competitor a version
  and checksum, a model a Hugging Face commit and its license. Unpinned downloads are not
  accepted. Python stacks use hash-pinned files that are not named `*requirements*.txt`.
- **No remote code.** Models that need `trust_remote_code` load through their official ONNX
  files or are not added.
- **Heavy runs never run on pull requests.** They are `workflow_dispatch` (or scheduled) only, so
  pull request CI stays within about 15 minutes.
- **Results** are only published from the fixed benchmark machine, with the machine fields kept
  beside the table. Numbers from a laptop or a hosted runner are labelled development-only.
