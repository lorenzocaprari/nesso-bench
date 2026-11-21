# nesso-bench

Reproducible retrieval benchmarks for [nesso](https://github.com/lorenzocaprari/nesso), the offline
semantic search CLI for logs. This repository measures nesso against the tools people use
instead (grep, ripgrep, SQLite BM25, OpenSearch, a FAISS stack, xerj, ck, vecgrep) and against
other embedding models, on public log data with labels we did not write.

Everything here can be rerun by anyone: inputs are pinned by checksum, tools and models by
version or commit, and every report records the machine and the versions that produced it.
Reports say where nesso loses, too. [docs/method.md](docs/method.md) lists the rules we follow and
what these results cannot show.

## What is measured

- **Retrieval quality**: recall@10, MRR, nDCG@10, precision@10, and the rank of the first
  correct line, per query class.
- **Speed and memory**: index time and peak RSS, query latency (p50, p95) and peak RSS, index
  size against the raw log, and cold time to first result.

## Data

- **Loghub 2k seed sets** (HDFS, BGL, Thunderbird, OpenSSH, Linux, Apache), and three more
  with other log shapes (Hadoop, OpenStack, HealthApp), from
  [logpai/loghub](https://github.com/logpai/loghub), with small labelled query sets. Good for
  regression checks; too small to show customers.
- **Needle windows** from [Loghub 2.0](https://zenodo.org/records/8275861) (CC-BY-4.0): 100,000
  and 1,000,000-line windows of the BGL and Thunderbird logs. A query's correct answers are the
  lines the system administrators tagged with an alert category (A. Oliner and J. Stearley,
  "What Supercomputers Say", DSN 2007), so the labels are not ours.

Loghub data is for research use and is downloaded on demand, never committed.

## Results policy

Numbers from a laptop or a hosted CI runner are for development only: hosted runners are too
noisy to publish timings. Published results come from one fixed machine and carry its platform
fields, the tool versions, and digests of the models used.

## Layout

| Path | What |
| --- | --- |
| `scripts/` | The harness (`eval-retrieval`, `eval-retrieval-compare`, `eval-retrieval-merge`, `eval-results-render`, `fetch-loghub`), the pinned installers (`install-nesso` for a released nesso, `install-competitors`), the one-command `scorecard` run for the benchmark machine, and lint wrappers |
| `test/eval/` | 2k seed query sets, needle queries, and `reference/`: committed competitor reports that nesso's CI compares against |
| `test/scripts/` | Harness unit tests |
| `bench/competitors/` | Optional competitor stacks, hash-pinned |
| `docs/` | How each benchmark works ([eval.md](docs/eval.md)), the rules and limits of the results ([method.md](docs/method.md)), and published results |

## Development

```bash
python3 -m pip install pre-commit==4.7.0
bash scripts/lint        # hygiene and ruff
bash scripts/actionlint  # workflow syntax (pinned binary)
bash scripts/zizmor      # workflow security (pinned binary)
bash scripts/test        # unit tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under Apache-2.0.
