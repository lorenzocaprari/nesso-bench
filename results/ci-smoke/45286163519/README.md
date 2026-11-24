# Scorecard smoke timing report (development-only)

**Development-only. Do not publish or quote these timings as a benchmark result.** Measured on shared GitHub-hosted runners. Published results come from the fixed benchmark machine.

- Run: [45286163519](https://github.com/lorenzocaprari/nesso-bench/actions/runs/45286163519) (`workflow_dispatch`) at `dc2f9b341cc00e8954e963957bfd20ff43710e80`.
- nesso main: `0.3.1+gd86bdb3f98c5` from Package run [45186123708](https://github.com/lorenzocaprari/nesso/actions/runs/45186123708) at `d86bdb3f98c5f9772cdfecca82e1fe3f2c4df7c7`.
- nesso release scored in this run: `0.3.1`.
- Previous scheduled run: none is committed yet.

### Quality margins (deterministic)

Quality does not depend on the runner. The margin is nesso `auto` MRR minus the best other engine's MRR in this run (`scripts/eval-retrieval-compare --margins`). Compared with the `0.3.1` release scored in this run, and with the previous scheduled run.

| suite | system | class | main margin | main rival | 0.3.1 margin | 0.3.1 rival | Δ vs 0.3.1 | previous margin | previous rival | Δ vs previous |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2k | hdfs-2k | cause | -0.219 | ck | -0.243 | ck | +0.023 | — | — | — |
| 2k | hdfs-2k | exact_id | +0.000 | xerj | +0.000 | xerj | +0.000 | — | — | — |
| 2k | hdfs-2k | paraphrase | -0.031 | xerj-neural | +0.026 | xerj-neural | -0.057 | — | — | — |
| 2k | hdfs-2k | overall | +0.068 | bm25 | +0.080 | bm25 | -0.011 | — | — | — |
| 2k | bgl-2k | cause | +0.027 | xerj-neural | +0.042 | xerj-neural | -0.015 | — | — | — |
| 2k | bgl-2k | exact_id | +0.000 | ripgrep | +0.000 | ripgrep | +0.000 | — | — | — |
| 2k | bgl-2k | paraphrase | -0.094 | xerj-semantic | +0.000 | xerj-semantic | -0.094 | — | — | — |
| 2k | bgl-2k | overall | +0.064 | bm25 | +0.100 | bm25 | -0.036 | — | — | — |
| 2k | thunderbird-2k | cause | -0.026 | xerj-neural | +0.035 | xerj-neural | -0.060 | — | — | — |
| 2k | thunderbird-2k | exact_id | +0.000 | bm25 | +0.000 | bm25 | +0.000 | — | — | — |
| 2k | thunderbird-2k | paraphrase | -0.003 | bm25 | +0.039 | bm25 | -0.042 | — | — | — |
| 2k | thunderbird-2k | overall | +0.060 | bm25 | +0.094 | bm25 | -0.034 | — | — | — |
| 2k | openssh-2k | cause | +0.003 | xerj-neural | -0.069 | xerj-neural | +0.072 | — | — | — |
| 2k | openssh-2k | exact_id | -0.030 | xerj-semantic | +0.000 | xerj-semantic | -0.030 | — | — | — |
| 2k | openssh-2k | paraphrase | -0.060 | xerj-neural | -0.119 | xerj-neural | +0.059 | — | — | — |
| 2k | openssh-2k | overall | +0.063 | bm25 | +0.030 | bm25 | +0.034 | — | — | — |
| 2k | linux-2k | cause | +0.007 | xerj-neural | -0.006 | xerj-neural | +0.013 | — | — | — |
| 2k | linux-2k | exact_id | -0.020 | ripgrep | -0.020 | ripgrep | +0.000 | — | — | — |
| 2k | linux-2k | paraphrase | +0.020 | xerj-neural | -0.032 | xerj-neural | +0.052 | — | — | — |
| 2k | linux-2k | overall | +0.165 | bm25 | +0.143 | bm25 | +0.022 | — | — | — |
| 2k | apache-2k | cause | -0.041 | vecgrep | +0.010 | vecgrep | -0.050 | — | — | — |
| 2k | apache-2k | exact_id | +0.000 | xerj | +0.000 | xerj | +0.000 | — | — | — |
| 2k | apache-2k | paraphrase | -0.059 | bm25 | -0.059 | bm25 | +0.000 | — | — | — |
| 2k | apache-2k | overall | +0.036 | bm25 | +0.051 | bm25 | -0.015 | — | — | — |
| 2k | overall | cause | +0.006 | xerj-neural | +0.006 | xerj-neural | -0.000 | — | — | — |
| 2k | overall | exact_id | -0.008 | bm25 | -0.003 | bm25 | -0.005 | — | — | — |
| 2k | overall | paraphrase | -0.005 | xerj-neural | +0.010 | xerj-neural | -0.014 | — | — | — |
| 2k | overall | overall | +0.078 | bm25 | +0.084 | bm25 | -0.006 | — | — | — |
| formats | hadoop-2k | cause | +0.009 | opensearch-knn | -0.058 | opensearch-knn | +0.068 | — | — | — |
| formats | hadoop-2k | exact_id | +0.000 | xerj | -0.500 | xerj | +0.500 | — | — | — |
| formats | hadoop-2k | paraphrase | +0.069 | xerj-neural | -0.005 | xerj-neural | +0.074 | — | — | — |
| formats | hadoop-2k | overall | +0.192 | bm25 | -0.022 | bm25 | +0.214 | — | — | — |
| formats | openstack-2k | cause | +0.000 | xerj-neural | +0.020 | xerj-neural | -0.020 | — | — | — |
| formats | openstack-2k | exact_id | +0.000 | ripgrep | +0.000 | ripgrep | +0.000 | — | — | — |
| formats | openstack-2k | paraphrase | +0.042 | bm25 | +0.042 | bm25 | +0.000 | — | — | — |
| formats | openstack-2k | overall | +0.065 | bm25 | +0.072 | bm25 | -0.007 | — | — | — |
| formats | healthapp-2k | cause | +0.000 | xerj-neural | +0.052 | xerj-neural | -0.052 | — | — | — |
| formats | healthapp-2k | exact_id | +0.000 | xerj | +0.000 | xerj | +0.000 | — | — | — |
| formats | healthapp-2k | paraphrase | +0.122 | xerj-neural | +0.122 | xerj-neural | +0.000 | — | — | — |
| formats | healthapp-2k | overall | +0.269 | bm25 | +0.286 | bm25 | -0.017 | — | — | — |
| formats | overall | cause | +0.003 | opensearch-knn | +0.005 | opensearch-knn | -0.002 | — | — | — |
| formats | overall | exact_id | +0.000 | ripgrep | -0.167 | ripgrep | +0.167 | — | — | — |
| formats | overall | paraphrase | +0.092 | xerj-neural | +0.067 | xerj-neural | +0.025 | — | — | — |
| formats | overall | overall | +0.175 | bm25 | +0.112 | bm25 | +0.063 | — | — | — |
| json | hdfs-2k-json | cause | -0.156 | ck | -0.156 | ck | +0.000 | — | — | — |
| json | hdfs-2k-json | exact_id | +0.000 | xerj | +0.000 | xerj | +0.000 | — | — | — |
| json | hdfs-2k-json | paraphrase | -0.041 | vecgrep | +0.059 | vecgrep | -0.100 | — | — | — |
| json | hdfs-2k-json | overall | +0.056 | bm25 | +0.090 | bm25 | -0.033 | — | — | — |
| json | overall | cause | -0.156 | ck | -0.156 | ck | +0.000 | — | — | — |
| json | overall | exact_id | +0.000 | xerj | +0.000 | xerj | +0.000 | — | — | — |
| json | overall | paraphrase | -0.041 | vecgrep | +0.059 | vecgrep | -0.100 | — | — | — |
| json | overall | overall | +0.056 | bm25 | +0.090 | bm25 | -0.033 | — | — | — |
| bundle | support-bundle | cause | -0.050 | vecgrep | -0.092 | vecgrep | +0.042 | — | — | — |
| bundle | support-bundle | exact_id | +0.000 | xerj | +0.000 | xerj | +0.000 | — | — | — |
| bundle | support-bundle | paraphrase | +0.083 | xerj-neural | +0.042 | xerj-neural | +0.042 | — | — | — |
| bundle | support-bundle | overall | +0.069 | xerj | +0.042 | xerj | +0.028 | — | — | — |
| bundle | overall | cause | -0.050 | vecgrep | -0.092 | vecgrep | +0.042 | — | — | — |
| bundle | overall | exact_id | +0.000 | xerj | +0.000 | xerj | +0.000 | — | — | — |
| bundle | overall | paraphrase | +0.083 | xerj-neural | +0.042 | xerj-neural | +0.042 | — | — | — |
| bundle | overall | overall | +0.069 | xerj | +0.042 | xerj | +0.028 | — | — | — |
| bgl-needle-100k | bgl-needle-100k | keyword | +0.000 | xerj | +0.000 | xerj | +0.000 | — | — | — |
| bgl-needle-100k | bgl-needle-100k | symptom | +0.175 | bm25 | +0.138 | bm25 | +0.037 | — | — | — |
| bgl-needle-100k | bgl-needle-100k | overall | +0.087 | bm25 | +0.069 | bm25 | +0.018 | — | — | — |
| bgl-needle-100k | overall | keyword | +0.000 | xerj | +0.000 | xerj | +0.000 | — | — | — |
| bgl-needle-100k | overall | symptom | +0.175 | bm25 | +0.138 | bm25 | +0.037 | — | — | — |
| bgl-needle-100k | overall | overall | +0.087 | bm25 | +0.069 | bm25 | +0.018 | — | — | — |

Δ is this run's nesso main margin minus the other margin. Positive means main leads the best other engine by more (or trails it by less). A different rival means the best other engine changed.

### In-job timing ratios (development-only, one runner)

ripgrep, BM25, OpenSearch, and xerj BM25 ran in the nesso job, on the same runner as nesso main and nesso `0.3.1`. Each ratio is that engine's time divided by the reference. Above 1× the engine is slower. Query p50 uses nesso mode `auto` and is the median of the per-dataset ratios. Index ratios sum index wall time over the datasets both finished. grep is the grep measured in the nesso main run; a dataset that run did not measure uses the release run's grep, still the same job. grep and ripgrep do not build an index, so index ratios are against nesso only. An engine is not ratioed to itself.

nesso main is `0.3.1+gd86bdb3f98c5`. The release column is nesso `0.3.1`.

CPU: Intel(R) Xeon(R) 6975P-C.

| suite | engine | index s | index ÷ nesso main | index ÷ nesso release | query p50 s | p50 ÷ nesso main | p50 ÷ nesso release | p50 ÷ grep | p50 ÷ ripgrep |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2k | ripgrep | — | — | — | 0.005 | 0.02× | 0.02× | 1.63× | — |
| 2k | bm25 | 0.630 | 0.16× | 0.06× | 0.000 | 0.00× | 0.00× | 0.10× | 0.06× |
| 2k | xerj | 1.850 | 0.46× | 0.18× | 0.001 | 0.00× | 0.00× | 0.35× | 0.21× |
| formats | ripgrep | — | — | — | 0.006 | 0.03× | 0.03× | 1.56× | — |
| formats | bm25 | 0.330 | 0.15× | 0.12× | 0.000 | 0.00× | 0.00× | 0.10× | 0.07× |
| formats | opensearch | 49.1 | 22.3× | 18.0× | 0.007 | 0.03× | 0.03× | 1.86× | 1.19× |
| formats | xerj | 0.920 | 0.42× | 0.34× | 0.001 | 0.00× | 0.00× | 0.30× | 0.19× |
| json | ripgrep | — | — | — | 0.006 | 0.03× | 0.03× | 1.59× | — |
| json | bm25 | 0.110 | 0.27× | 0.26× | 0.001 | 0.00× | 0.00× | 0.27× | 0.17× |
| json | opensearch | 16.3 | 39.8× | 37.9× | 0.005 | 0.02× | 0.02× | 1.38× | 0.87× |
| json | xerj | 0.310 | 0.76× | 0.72× | 0.001 | 0.01× | 0.00× | 0.30× | 0.19× |
| bgl-needle-100k | ripgrep | — | — | — | 0.020 | 0.05× | 0.04× | 1.21× | — |
| bgl-needle-100k | bm25 | 0.550 | 0.19× | 0.01× | 0.006 | 0.02× | 0.01× | 0.35× | 0.29× |
| bgl-needle-100k | opensearch | 20.1 | 6.87× | 0.29× | 0.006 | 0.02× | 0.01× | 0.38× | 0.32× |
| bgl-needle-100k | xerj | 3.830 | 1.31× | 0.06× | 0.001 | 0.00× | 0.00× | 0.07× | 0.06× |

### Embedding engines, one job each (development-only)

diy-faiss, OpenSearch k-NN, xerj-neural, xerj-semantic, ck, and vecgrep each ran in their own job. A timing from one job is not compared with a timing from another, nor with nesso. An engine is shown only as its own trend, and only after 4 kept runs measured that suite. Until then the seconds stay in `report.json` so a later run can complete the trend, and are not shown here.

#### diy-faiss

`diy-faiss` `2k`: 1 of 4 runs kept. No timing shown.

`diy-faiss` `formats`: 1 of 4 runs kept. No timing shown.

`diy-faiss` `json`: 1 of 4 runs kept. No timing shown.

#### opensearch-knn

`opensearch-knn` `2k`: 1 of 4 runs kept. No timing shown.

`opensearch-knn` `formats`: 1 of 4 runs kept. No timing shown.

`opensearch-knn` `json`: 1 of 4 runs kept. No timing shown.

#### xerj-neural

`xerj-neural` `2k`: 1 of 4 runs kept. No timing shown.

`xerj-neural` `formats`: 1 of 4 runs kept. No timing shown.

`xerj-neural` `json`: 1 of 4 runs kept. No timing shown.

#### xerj-semantic

`xerj-semantic` `2k`: 1 of 4 runs kept. No timing shown.

`xerj-semantic` `formats`: 1 of 4 runs kept. No timing shown.

`xerj-semantic` `json`: 1 of 4 runs kept. No timing shown.

`xerj-semantic` `bgl-needle-100k`: 1 of 4 runs kept. No timing shown.

#### ck

`ck` `2k`: 1 of 4 runs kept. No timing shown.

`ck` `json`: 1 of 4 runs kept. No timing shown.

#### vecgrep

`vecgrep` `2k`: 1 of 4 runs kept. No timing shown.

`vecgrep` `formats`: 1 of 4 runs kept. No timing shown.

`vecgrep` `json`: 1 of 4 runs kept. No timing shown.
