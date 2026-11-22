# Scorecard smoke timings, 21 Nov 2026 (development-only)

**Development-only. Do not publish or quote as a benchmark result.** These numbers come from one
run of the [Scorecard smoke](../../../.github/workflows/scorecard-smoke.yml) workflow on shared
GitHub-hosted runners. That workflow checks that the scorecard pipeline works; it is not a
benchmark. Published results come only from the fixed benchmark machine
([CONTRIBUTING.md](../../../CONTRIBUTING.md)).

- Run: [44953648512](https://github.com/lorenzocaprari/nesso-bench/actions/runs/44953648512),
  `workflow_dispatch` on `main` at `572113a`, 21 Nov 2026 21:50–23:17 UTC, conclusion success.
- Settings: `scripts/scorecard --dev --repeat 1 --memory-max 12G`, `nesso_version=0.3.1` (int8
  model `afdb6f1a0e45`). The `oom` job runs vecgrep on `bgl-needle-100k` under a 3 GB cap.
- The workflow artifacts (`scorecard-smoke-<group>`) expire on 5 Dec 2026. This folder keeps
  `raw/`, `status.json`, and `machine.json` from each artifact. `merged/` is left out because each
  group's `merged/<suite>.json` is a byte copy of its single `raw/<suite>/<group>.json`.
  The JSON files are as downloaded. The `.log` files lost the trailing spaces of their text
  tables to the repository's whitespace hook.

## How to read it

- **Each engine group ran in its own job on a different runner**, with different CPUs (see
  the tables below). Timings from two groups are not comparable. The only like-for-like pair
  is nesso against grep, because they ran in the same job.
- `--repeat 1`: every figure is one sample, with no spread.
- `query p50` is the median per-query latency inside the query child (`docs/eval.md`, Retrieval
  eval `--measure`). nesso, ck, and vecgrep run one CLI process per query, so their latency
  includes process start, model load, and corpus open. xerj and OpenSearch answer from a running
  node.
- The suite tables summarise each group's `measure` section over that suite's measured
  datasets. Index wall time is summed, index ÷ log is total index bytes over total log bytes, peak
  RSS is the maximum, query p50 is the median of the per-dataset medians, and p95 is the
  maximum. The full per-dataset numbers are in `raw/<suite>/<group>.json`.

## Outcomes

### Scorecard runs

| group | CPU | logical CPUs | RAM | memory cap | development only |
| --- | --- | --- | --- | --- | --- |
| bm25 | AMD EPYC 7763 64-Core Processor | 4 | 16 GiB | 12G | yes |
| ck | Intel(R) Xeon(R) 6975P-C | 4 | 15 GiB | 12G | yes |
| diy-faiss | Intel(R) Xeon(R) 6975P-C | 4 | 15 GiB | 12G | yes |
| nesso | Intel(R) Xeon(R) 6975P-C | 4 | 15 GiB | 12G | yes |
| oom | Intel(R) Xeon(R) 6975P-C | 4 | 15 GiB | 3G | yes |
| opensearch | Intel(R) Xeon(R) 6975P-C | 4 | 15 GiB | 12G | yes |
| opensearch-knn | Intel(R) Xeon(R) 6975P-C | 4 | 15 GiB | 12G | yes |
| ripgrep | Intel(R) Xeon(R) 6975P-C | 4 | 15 GiB | 12G | yes |
| vecgrep | AMD EPYC 7763 64-Core Processor | 4 | 16 GiB | 12G | yes |
| xerj | Intel(R) Xeon(R) 6975P-C | 4 | 15 GiB | 12G | yes |
| xerj-neural | Intel(R) Xeon(R) 6975P-C | 4 | 15 GiB | 12G | yes |
| xerj-semantic | AMD EPYC 9V45 96-Core Processor | 4 | 16 GiB | 12G | yes |

| engine group | 2k | formats | json | bundle | bgl-needle-100k |
| --- | --- | --- | --- | --- | --- |
| bm25 | ok (3 s) | ok (2 s) | ok (1 s) | ok (0 s) | ok (4 s) |
| ck | ok (15 min) | out-of-memory (12G) (90 s) | ok (4 min) | out-of-memory (12G) (31 s) | — |
| diy-faiss | ok (7 min) | ok (5 min) | ok (116 s) | ok (113 s) | — |
| nesso | ok (10 min) | ok (3 min) | ok (103 s) | ok (50 s) | ok (5 min) |
| vecgrep | ok (8 min) | ok (4 min) | ok (112 s) | ok (85 s) | out-of-memory (3G) (8 s) |
| opensearch | ok (5 min) | ok (2 min) | ok (61 s) | ok (16 s) | ok (72 s) |
| opensearch-knn | ok (14 min) | ok (9 min) | ok (3 min) | ok (2 min) | — |
| ripgrep | ok (5 s) | ok (2 s) | ok (1 s) | ok (1 s) | ok (2 s) |
| xerj | ok (7 s) | ok (3 s) | ok (2 s) | ok (1 s) | ok (15 s) |
| xerj-neural | ok (20 min) | ok (17 min) | ok (6 min) | ok (14 min) | — |
| xerj-semantic | ok (15 s) | ok (7 s) | ok (2 s) | ok (5 s) | ok (63 s) |

48 of 51 runs ok.

| suite | group | outcome | exit code |
| --- | --- | --- | --- |
| formats | ck | out-of-memory (12G) | -15 |
| bundle | ck | out-of-memory (12G) | -15 |
| bgl-needle-100k | vecgrep | out-of-memory (3G) | -15 |

## Timings by suite

### 2k

| engine | datasets | lines | index wall s (sum) | index ÷ log | index peak RSS MiB (max) | query p50 s (median) | query p95 s (max) | query peak RSS MiB (max) | runner CPU |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| bm25 | 6 | 12,000 | 0.830 | 1.92 | 37 | 0.001 | 0.002 | 36 | AMD EPYC 7763 |
| ck | 6 | 12,000 | 184.5 | 1.68 | 7501 | 0.423 | 0.452 | 216 | Intel Xeon 6975P-C |
| diy-faiss | 6 | 12,000 | 129.2 | 11.94 | 835 | 0.008 | 0.010 | 570 | Intel Xeon 6975P-C |
| nesso (auto) | 6 | 12,000 | 10.4 | 4.51 | 223 | 0.228 | 0.238 | 116 | Intel Xeon 6975P-C |
| nesso (dense) | 6 | 12,000 | 10.4 | 4.51 | 223 | 0.227 | 0.238 | 116 | Intel Xeon 6975P-C |
| nesso (lexical) | 6 | 12,000 | 10.4 | 4.51 | 223 | 0.227 | 0.241 | 116 | Intel Xeon 6975P-C |
| opensearch | 6 | 12,000 | 87.2 | 1.82 | 1493 | 0.005 | 0.019 | 1474 | Intel Xeon 6975P-C |
| opensearch-knn | 6 | 12,000 | 235.0 | 14.76 | 1534 | 0.016 | 0.033 | 1564 | Intel Xeon 6975P-C |
| ripgrep | 6 | 12,000 | — | — | — | 0.005 | 0.007 | 36 | Intel Xeon 6975P-C |
| vecgrep | 6 | 12,000 | 70.8 | 7.57 | 3048 | 0.284 | 0.314 | 247 | AMD EPYC 7763 |
| xerj | 6 | 12,000 | 1.7 | 2.60 | 73 | 0.001 | 0.001 | 98 | Intel Xeon 6975P-C |
| xerj-neural | 6 | 12,000 | 297.5 | 50.63 | 509 | 0.012 | 0.017 | 508 | Intel Xeon 6975P-C |
| xerj-semantic | 6 | 12,000 | 4.3 | 38.61 | 130 | 0.002 | 0.002 | 125 | AMD EPYC 9V45 |

### formats

| engine | datasets | lines | index wall s (sum) | index ÷ log | index peak RSS MiB (max) | query p50 s (median) | query p95 s (max) | query peak RSS MiB (max) | runner CPU |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| bm25 | 3 | 6,000 | 0.770 | 1.71 | 38 | 0.001 | 0.002 | 36 | AMD EPYC 7763 |
| diy-faiss | 3 | 6,000 | 105.9 | 7.89 | 781 | 0.008 | 0.012 | 570 | Intel Xeon 6975P-C |
| nesso (auto) | 3 | 6,000 | 2.7 | 1.53 | 169 | 0.225 | 0.231 | 114 | Intel Xeon 6975P-C |
| nesso (dense) | 3 | 6,000 | 2.7 | 1.53 | 169 | 0.225 | 0.230 | 114 | Intel Xeon 6975P-C |
| nesso (lexical) | 3 | 6,000 | 2.7 | 1.53 | 169 | 0.225 | 0.230 | 114 | Intel Xeon 6975P-C |
| opensearch | 3 | 6,000 | 44.6 | 1.17 | 1478 | 0.005 | 0.021 | 1472 | Intel Xeon 6975P-C |
| opensearch-knn | 3 | 6,000 | 147.8 | 9.26 | 1553 | 0.015 | 0.040 | 1540 | Intel Xeon 6975P-C |
| ripgrep | 3 | 6,000 | — | — | — | 0.006 | 0.008 | 38 | Intel Xeon 6975P-C |
| vecgrep | 3 | 6,000 | 49.2 | 5.37 | 3722 | 0.288 | 0.315 | 247 | AMD EPYC 7763 |
| xerj | 3 | 6,000 | 0.870 | 2.09 | 79 | 0.001 | 0.001 | 93 | Intel Xeon 6975P-C |
| xerj-neural | 3 | 6,000 | 260.7 | 32.88 | 456 | 0.014 | 0.022 | 452 | Intel Xeon 6975P-C |
| xerj-semantic | 3 | 6,000 | 1.7 | 24.73 | 123 | 0.002 | 0.003 | 130 | AMD EPYC 9V45 |

### json

| engine | datasets | lines | index wall s (sum) | index ÷ log | index peak RSS MiB (max) | query p50 s (median) | query p95 s (max) | query peak RSS MiB (max) | runner CPU |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| bm25 | 1 | 2,000 | 0.140 | 1.77 | 37 | 0.002 | 0.003 | 36 | AMD EPYC 7763 |
| ck | 1 | 2,000 | 51.0 | 1.86 | 7470 | 0.420 | 0.432 | 216 | Intel Xeon 6975P-C |
| diy-faiss | 1 | 2,000 | 37.3 | 7.72 | 782 | 0.008 | 0.010 | 569 | Intel Xeon 6975P-C |
| nesso (auto) | 1 | 2,000 | 0.410 | 0.87 | 143 | 0.223 | 0.225 | 113 | Intel Xeon 6975P-C |
| nesso (dense) | 1 | 2,000 | 0.410 | 0.87 | 143 | 0.224 | 0.226 | 113 | Intel Xeon 6975P-C |
| nesso (lexical) | 1 | 2,000 | 0.410 | 0.87 | 143 | 0.223 | 0.227 | 113 | Intel Xeon 6975P-C |
| opensearch | 1 | 2,000 | 15.0 | 1.32 | 1461 | 0.004 | 0.008 | 1465 | Intel Xeon 6975P-C |
| opensearch-knn | 1 | 2,000 | 50.2 | 8.87 | 1518 | 0.012 | 0.027 | 1510 | Intel Xeon 6975P-C |
| ripgrep | 1 | 2,000 | — | — | — | 0.006 | 0.006 | 36 | Intel Xeon 6975P-C |
| vecgrep | 1 | 2,000 | 22.9 | 5.29 | 3683 | 0.286 | 0.294 | 247 | AMD EPYC 7763 |
| xerj | 1 | 2,000 | 0.310 | 2.29 | 76 | 0.001 | 0.001 | 99 | Intel Xeon 6975P-C |
| xerj-neural | 1 | 2,000 | 82.6 | 32.57 | 470 | 0.013 | 0.016 | 473 | Intel Xeon 6975P-C |
| xerj-semantic | 1 | 2,000 | 0.540 | 24.58 | 116 | 0.002 | 0.002 | 128 | AMD EPYC 9V45 |

### bgl-needle-100k

| engine | datasets | lines | index wall s (sum) | index ÷ log | index peak RSS MiB (max) | query p50 s (median) | query p95 s (max) | query peak RSS MiB (max) | runner CPU |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| bm25 | 1 | 100,000 | 0.810 | 1.80 | 73 | 0.009 | 0.063 | 73 | AMD EPYC 7763 |
| nesso (auto) | 1 | 100,000 | 68.8 | 2.93 | 315 | 0.469 | 0.476 | 212 | Intel Xeon 6975P-C |
| nesso (dense) | 1 | 100,000 | 68.8 | 2.93 | 315 | 0.457 | 0.461 | 212 | Intel Xeon 6975P-C |
| nesso (lexical) | 1 | 100,000 | 68.8 | 2.93 | 315 | 0.473 | 0.490 | 220 | Intel Xeon 6975P-C |
| opensearch | 1 | 100,000 | 18.0 | 0.48 | 1481 | 0.006 | 0.031 | 1478 | Intel Xeon 6975P-C |
| ripgrep | 1 | 100,000 | — | — | — | 0.017 | 0.045 | 84 | Intel Xeon 6975P-C |
| xerj | 1 | 100,000 | 3.7 | 1.76 | 553 | 0.001 | 0.003 | 529 | Intel Xeon 6975P-C |
| xerj-semantic | 1 | 100,000 | 16.1 | 18.04 | 1009 | 0.002 | 0.006 | 1040 | AMD EPYC 9V45 |
