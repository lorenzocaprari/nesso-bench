# Retrieval evaluation

How the retrieval benchmarks in this repository work: datasets, engines, metrics, and how to run them. Imported from nesso's `docs/benchmarks.md`; nesso's own speed and memory regression benchmarks stay documented there.

`scripts/eval-retrieval` scores `nesso search --json -k 10` against labelled queries on the pinned Loghub 2k samples (HDFS, BGL, Thunderbird, OpenSSH, Linux, Apache). Pass `--dataset all-2k` (or a comma-separated list such as `hdfs-2k,bgl-2k`) to select systems; each maps to its log, structured CSV, and `test/eval/queries/<system>_2k.jsonl` seed file. Without `--dataset`, the defaults stay the HDFS_2k paths. It indexes each selected log once, runs each query for the requested modes (default `auto`, `hybrid`, `dense`, `lexical`), and reports recall@10, MRR, and nDCG@10. A query sets exactly one of `relevant_lines` (1-based LineIds) or `relevant_events` (Loghub EventIds from the structured CSV that `scripts/fetch-loghub` also downloads). The relevant set R is the listed lines, or every line whose EventId is listed. Gains are binary on lines: recall@10 is `|top 10 ∩ R| / min(10, |R|)`, MRR is `1 / rank` of the first line in R (0 if none), and nDCG@10 is DCG@10 divided by the ideal DCG of `min(10, |R|)` relevant lines. Exact-ID seeds use `relevant_lines`. Paraphrase and cause seeds use `relevant_events`. Each listed line must exist and contain the query as a whole token. The CSV row count must equal the log line count so LineId matches nesso's 1-based lines. The script prints one text table per system plus an overall table, and writes deterministic JSON (`schema_version` 3, per-dataset modes and an overall aggregate, per-query `ranked_lines`) to `--out`. It is report-only: any scores exit 0; it fails only on missing inputs, a bad query file, a line label or CSV alignment check that fails, or unparseable search output. The committed seed sets in `test/eval/queries/` are for local smoke scoring and are not the published retrieval benchmark. [`.github/workflows/eval-retrieval.yml`](https://github.com/lorenzocaprari/nesso/blob/main/.github/workflows/eval-retrieval.yml) runs that report with nesso, grep, and BM25 (`--engine nesso --engine grep --engine bm25`), plus the `bgl-needle-100k` needle window with nesso (`auto`, `dense`, `lexical`), grep, and BM25. It checks out this repository at the commit pinned in that workflow, so a change here reaches nesso only when nesso bumps the pin. It runs on schedule `47 6 * * *` (main only), on `workflow_dispatch`, and on nesso pull requests that change `src/`, `CMakeLists.txt`, `conanfile.py`, `conan.lock`, `scripts/fetch-model`, or the workflow itself (which holds the pin). It is not a Pipeline job and not part of the `CI gate`; scores never fail it. It does not write `gh-pages` yet.

```bash
./scripts/fetch-loghub --dataset all-2k
python3 scripts/eval-retrieval --dataset all-2k --out build/eval/all_2k.json
```

The nesso binary comes from `--binary`, else `NESSO_BINARY`, else a nesso build tree, and the model from `--model-dir`, else `NESSO_MODEL_DIR`, else `models/`. Published numbers score a released nesso, not a development build. `scripts/install-nesso VERSION` downloads `nesso_<VERSION>_<arch>.deb` from the nesso GitHub release, checks it against the sha256 pinned in the script (the digest in that release's `SHA256SUMS`), and unpacks the binary and the shipped int8 model under `build/nesso/nesso-<VERSION>-<arch>/`. Nothing is installed system-wide. It prints `export` lines for `NESSO_BINARY`, `NESSO_MODEL_DIR`, and `PATH`. It uses `dpkg-deb` when present, else `ar` and `tar` (zstd needed for the data member). The architecture defaults to this machine's (`--arch amd64|arm64`). To benchmark a new release, add its two `.deb` digests to the script. `--fp32` also stages the fp32 build of the same model under `build/nesso/nesso-<VERSION>-<arch>/fp32/` and exports `NESSO_FP32_MODEL_DIR`. The shipped int8 model is Xenova's `model_quantized.onnx` of all-MiniLM-L6-v2; the fp32 one is `model.onnx` from the same commit, with the sha256 nesso's `scripts/fetch-model` pins for its fp32 determinism gate. The shipped `vocab.txt` must match nesso's vocabulary pin, and is copied next to it. Passing that directory as `--model-dir` scores the released binary with the fp32 model, so the cost of the quantization is measured on the binary users get.

```bash
eval "$(scripts/install-nesso 0.3.1)"
python3 scripts/eval-retrieval --dataset all-2k --engine nesso --out build/eval/all_2k_v0.3.1.json
```

Optional keyword and DIY semantic baselines share the same labels and metrics. Pass `--engine` repeatedly (`nesso`, `grep`, `ripgrep`, `bm25`, `diy-faiss`, `xerj`, `xerj-neural`, `opensearch`, `opensearch-knn`, `ck`, `vecgrep`; default is nesso only). Without `--engine` (or with `--engine nesso` alone) the JSON stays `schema_version` 3 and is byte-compatible with prior nesso-only reports. Any other engine writes `schema_version` 4 with an `engines[]` axis and a side-by-side text table. Scoring is unchanged: each engine only supplies ranked 1-based line ids.

- **grep:** `grep -n -F -i -e <query> -- <log>`. If that has no hits, OR the query's whitespace tokens with one `-e` per token. Rank is file order (ascending line id), top 10. This is the "what people do today" baseline.
- **ripgrep:** the same rule with `rg -n -F -i`. It ranks exactly like grep, so its scores equal grep's; it is there to measure speed and memory against the tool people actually use. `scripts/install-competitors ripgrep` installs the pinned ripgrep (see below). If `rg` is missing, the engine is reported as `skipped` (not zeros).
- **bm25:** Python stdlib `sqlite3` FTS5, one row per line with `rowid = line id`, query = OR of FTS5-quoted tokens, `ORDER BY bm25(lines), rowid LIMIT 10`. The run fails clearly if the sqlite3 build lacks FTS5.
- **diy-faiss:** the stack a team would hack together — Hugging Face `sentence-transformers/all-MiniLM-L6-v2` at the pinned revision in `bench/competitors/diy_faiss.py` (fp32, `normalize_embeddings=True`), one vector per log line (no dedup, no masking), FAISS `IndexFlatIP`, top 10, ties broken by line id. CPU only, one thread, fixed seeds. The engine lives in `bench/competitors/diy_faiss.py` and is imported only when selected. Missing packages fail with an install hint. The report's diy-faiss entry records `versions` (model revision plus sentence-transformers, torch, and faiss). Dependencies are hash-pinned in `bench/competitors/diy-faiss.hashes.txt` for a local venv; they are not in the build image, Pipeline, or the nightly job. The pin file avoids the `*requirements*.txt` name so PR dependency-review does not index it.
- **xerj-semantic:** xerj's out-of-the-box semantic search. `text` is mapped as `semantic_text` and queried with `semantic`, like xerj-neural, but the node keeps xerj's default embedder (lexical feature hashing, offline, no model files). It needs a node that is not in `--embed-mode neural`: in a run that also selects xerj-neural, the shared spawned node is neural, so xerj-semantic reports `skipped`. Run it on its own (the eval-competitors workflow does).
- **xerj / xerj-neural:** [XERJ](https://github.com/xerj-org/xerj) over its Elasticsearch-compatible API (stdlib `urllib` only). One document per log line (`_id` = line id, fields `line` and `text`). `xerj` uses a plain `match` on `text` against the default lexical embedder (no custom analyzer). `xerj-neural` maps `text` as `semantic_text` and runs the documented `semantic` query; it needs the three MiniLM files staged locally (`--xerj-model-dir`) and never downloads them. Pass `--xerj-url http://127.0.0.1:9200` for an already running node, or `--xerj-bin` / `xerj` on `PATH` to spawn `--insecure --data-dir <tmp> --port <free>` (neural adds `--embed-mode neural` and a temp TOML `local_model_dir`). Missing URL and binary, or missing neural model files when spawning, report `skipped` (not zeros). Report `versions` carry xerj version, `url_mode` (`external` or `spawned`), index wall time, and `~90 MB` for neural. Local or per-release only — not Pipeline and not the nightly `eval-retrieval` job.
- **opensearch / opensearch-knn:** single-node [OpenSearch](https://opensearch.org/) (Apache-2.0), the self-hosted search incumbent, through the same stdlib HTTP adapter as xerj. Each index has one primary shard and no replica, so BM25 statistics are not split across shards. `opensearch` maps `text` with the default standard analyzer and runs a plain `match`. `opensearch-knn` stores one `knn_vector` (384 dimensions, HNSW, Lucene engine, `cosinesimil`, default parameters) per line. The vectors come from the same fp32 MiniLM revision and encoder as diy-faiss, computed in the eval process. It needs the diy-faiss venv and reports `skipped` with the install hint when that stack is missing. OpenSearch ML Commons in-engine models are not used. Pass `--opensearch-url http://127.0.0.1:9200` for a node you already run with security off, or `--opensearch-home` (or `OPENSEARCH_HOME`) to spawn one from an extracted tarball. The spawned node is `bin/opensearch` with `discovery.type=single-node`, `network.host=127.0.0.1`, free HTTP and transport ports, a temp `path.data` and `path.logs`, the disk watermark check off, `plugins.security.disabled=true` when the security plugin is installed, and `OPENSEARCH_JAVA_OPTS` (default `-Xms1g -Xmx1g`). With no URL and no home, both engines report `skipped`. A node without the `opensearch-knn` plugin reports `opensearch-knn` as `skipped`. Report `versions` carry `opensearch_version`, `url_mode`, index wall time, `java_opts`, and, for k-NN, the method, model, and revision. Local or per-release only — not Pipeline and not the nightly `eval-retrieval` job.
- **ck / vecgrep:** the two closest semantic-grep CLIs, [ck](https://github.com/BeaconBay/ck) (Apache-2.0) and [vecgrep](https://github.com/martintrojer/vecgrep) (MIT), run as installed, with their default models and chunking. Each gets its own corpus directory holding only a hard link (or copy) of the log, so its index stays out of the repository. vecgrep gets a `.vecgrep` directory there to pin its project root. The index step is `ck --index --quiet .` or `vecgrep --index-only --quiet`. Each query runs `ck --sem --jsonl --no-snippet --quiet --topk 10 --threshold 0 -- <query> <log>` or `vecgrep --json --quiet -k 10 --threshold 0 -- <query> <log>`. `--threshold 0` turns off ck's default 0.6 cutoff so both tools return their top 10 like every other engine. Both tools rank multi-line chunks, not lines. The adapter orders chunks by score, then start line. Each chunk contributes its lines in file order, a line that an earlier overlapping chunk already gave is skipped, and the list stops at 10 lines. So one strong chunk can fill the whole top 10. That is how a reader of their output sees it, and it is the main reason their line scores differ from nesso's. Missing executables report `skipped`. Report `versions` carry the tool's `--version` line. ck embeds with `BAAI/bge-small-en-v1.5` and downloads it to `$XDG_CACHE_HOME/ck` (or `~/.cache/ck`) on first use. vecgrep ships `all-MiniLM-L6-v2` inside the binary. Run ck once before `--measure` so the timed runs do not include that download. Local or per-release only — not Pipeline and not the nightly `eval-retrieval` job.

`scripts/install-competitors` installs the pinned competitors and checks every download against its pin: ripgrep 15.2.0 (the static x86_64 musl build, sha256), ck 0.8.1 (release binary, sha256), vecgrep v0.10.1 (built with `cargo install --locked` from the tag's commit, because its release binary needs glibc 2.43; the build needs cargo, `pkg-config`, and the OpenSSL headers, `libssl-dev` on Debian and Ubuntu), xerj 1.0.0-rc.104 (the static musl build, sha256), the three all-MiniLM-L6-v2 files xerj-neural uses (at the revision diy-faiss pins, sha256), the OpenSearch 3.10.0 full bundle (sha512; the min distribution has no k-NN plugin, and the bundle is about 1.1 GB), and the diy-faiss venv (`pip --require-hashes` from `bench/competitors/diy-faiss.hashes.txt`, Python 3.12; set `PYTHON` to pick the interpreter). Pass the engines to install (`diy-faiss`, `opensearch`, `opensearch-knn`, `ck`, `vecgrep`, `xerj`, `xerj-neural`, `xerj-semantic`, `ripgrep`, or `all`). grep and SQLite BM25 come from the system; their versions are recorded in a `--measure` report. Everything lands under `build/competitors/` (`--dest` to change it), and a piece already installed from the same pin is reused. The script prints `export` lines for `EVAL_PYTHON`, `OPENSEARCH_HOME`, `XERJ_MODEL_DIR`, and `PATH`, so `eval` sets up the shell:

```bash
eval "$(scripts/install-competitors ck vecgrep)"
python3 scripts/eval-retrieval --dataset all-2k \
  --engine nesso --engine ck --engine vecgrep --out build/eval/chunk_cli.json

eval "$(scripts/install-competitors opensearch-knn)"
PYTHONHASHSEED=0 "${EVAL_PYTHON}" scripts/eval-retrieval --dataset all-2k \
  --engine bm25 --engine diy-faiss --engine opensearch --engine opensearch-knn \
  --out build/eval/opensearch.json

eval "$(scripts/install-competitors xerj-neural)"
python3 scripts/eval-retrieval --dataset all-2k --engine xerj-neural \
  --xerj-model-dir "${XERJ_MODEL_DIR}" --out build/eval/xerj_neural.json
```

`scripts/eval-retrieval` never downloads a competitor itself. OpenSearch refuses to start as root. The bundled JDK means no system Java is needed.

Fairness for published comparisons: same logs, queries, machine, and k=10. DIY and opensearch-knn use the original Hub fp32 MiniLM; nesso uses the shipped int8 ONNX. Compare scores; do not expect identical vectors. opensearch-knn and diy-faiss share vectors, so a score gap between them comes from HNSW being approximate where FAISS `IndexFlatIP` is exact. OpenSearch peak RSS follows the JVM heap in `OPENSEARCH_JAVA_OPTS`; keep that value beside any published number.

```bash
python3 scripts/eval-retrieval --dataset all-2k \
  --engine nesso --engine grep --engine ripgrep --engine bm25 \
  --out build/eval/all_2k_baselines.json
```

```bash
eval "$(PYTHON=python3.12 scripts/install-competitors diy-faiss)"
PYTHONHASHSEED=0 "${EVAL_PYTHON}" scripts/eval-retrieval --dataset all-2k \
  --engine diy-faiss --out build/eval/diy_faiss.json
```

Set `NESSO_EVAL_DIY=1` to run the opt-in live diy-faiss unit test against a tiny fixture (requires the venv packages). Set `NESSO_EVAL_MEASURE=1` to run the opt-in measure smoke on HDFS 2k.

### Labelled Loghub 2.0 windows

The 2k seed sets are labelled by us and are small. For larger tasks with ground truth we did not write, `scripts/fetch-loghub` cuts windows out of the Loghub 2.0 BGL and Thunderbird logs (Zenodo record [8275861](https://zenodo.org/records/8275861), CC-BY-4.0). In those logs the first token of every line is the system administrators' alert tag: `-` for a normal line, otherwise an alert category such as `KERNDTLB`, `APPSEV`, or `EXT_FS`. The tags come from A. Oliner and J. Stearley, "What Supercomputers Say: A Study of Five System Logs", DSN 2007. Loghub 2.0 is from Z. Jiang et al., "A Large-scale Evaluation for Log Parsing Techniques: How Far Are We?", ISSTA 2024.

```bash
./scripts/fetch-loghub --dataset bgl-loghub2 --window 4100001:100000 --window 3200001:1000000
./scripts/fetch-loghub --dataset thunderbird-loghub2 --window 8550001:1000000
```

Each `--window START:COUNT` (1-based start line, repeatable) writes `build/bench/<Name>_loghub2_<start>_<count>.log` with the tag removed, so the alert category is never searchable text, and a `.labels` file with one tag per line. The archive (BGL 86 MB, Thunderbird 293 MB) is checked against its sha256 pin, read once for all windows, and deleted. The three windows above have pinned output hashes. A cached window that still matches its pin is kept, and a fresh write that does not match fails. Other windows are written unpinned.

| Window | Lines | Alert categories | Alert lines | Rarest categories |
| --- | --- | --- | --- | --- |
| BGL from 4,100,001 | 100,000 | 17 | 21,061 | KERNNOETH 1, LINKBLL 2, KERNSTOR 2, MONPOW 3 |
| BGL from 3,200,001 | 1,000,000 | 27 | 72,300 | KERNEXT 1, MMCS 1, LINKBLL 2, KERNSTOR 3 |
| Thunderbird from 8,550,001 | 1,000,000 | 5 | 32 | NMI 2, CPU 3, ECC 6, EXT_FS 8, SCSI 13 |

The windows were chosen to hold the most distinct alert categories at each size, scanning Loghub 2.0 in 50,000-line steps. Loghub data is for research use and stays out of the repository.

### Needle benchmark

`scripts/eval-retrieval --dataset bgl-needle-100k` (also `bgl-needle-1m`, `thunderbird-needle-1m`, or `all-needle`) scores engines on those windows. Each query names one alert category, and its relevant set is every line the administrators tagged with that category. We write the queries; we do not write the labels. The task is "something like this happened, show me the lines", with real distractors. The same message text often appears untagged at a lower severity, and on Thunderbird 32 alert lines sit among 1,000,000.

`test/eval/needles/bgl.jsonl` (27 categories) and `test/eval/needles/thunderbird.jsonl` (5 categories) hold two queries per category:

- `keyword`: the terse terms an engineer would grep for, for example `data TLB error`.
- `symptom`: an operator's description that avoids the log's own words where it can, for example `processor address translation cache fault`.

Each query records the category's `meaning` for review. The report prints each class's mean token `overlap` with the relevant lines, so a symptom query that drifts into the log's vocabulary shows up instead of hiding. Queries whose category is absent from a window are left out of that window, and categories without a query are listed.

Metrics per engine and class:

| Column | Meaning |
| --- | --- |
| `p@10` | Share of the top 10 lines that carry the category |
| `MRR`, `nDCG@10` | As in the 2k eval, on the tagged line set |
| `found@100` | Share of queries with at least one tagged line in the top 100 |
| `median 1st` | Median rank of the first tagged line, among queries that found one ("how far would I scroll") |
| `overlap` | Mean share of query tokens that occur in the tagged lines |

Every engine works here, nesso in each `--modes` value. diy-faiss, OpenSearch k-NN, ck, and vecgrep embed every line, which takes hours at 1,000,000 lines, so run them on `bgl-needle-100k`. The report is JSON with `"kind": "needle"` and its own `schema_version`; it is not the 2k report shape, and `scripts/eval-retrieval-compare` compares it only with another needle report. `--measure` works on needle datasets, see below. `bgl-needle-100k` with nesso, grep, and BM25 also runs in the `eval-retrieval` workflow (nightly and on pull requests); the 1M windows and the embedding baselines stay local or per release.

```bash
python3 scripts/eval-retrieval --dataset bgl-needle-100k \
  --engine nesso --engine grep --engine bm25 --out build/eval/needle_bgl_100k.json
python3 scripts/eval-retrieval --dataset thunderbird-needle-1m,bgl-needle-1m \
  --engine nesso --engine grep --engine bm25 --modes auto,dense,lexical --out build/eval/needle_1m.json
```

### Heavy competitors in CI

[`.github/workflows/eval-competitors.yml`](../.github/workflows/eval-competitors.yml) scores the competitors that are too heavy for every night on the 2k seed sets and on `bgl-needle-100k`. It measures retrieval quality only, with no `--measure`, because hosted-runner timings are too noisy to publish. Each of diy-faiss, opensearch, opensearch-knn, ck, vecgrep, xerj, xerj-neural, and xerj-semantic runs in its own job on `ubuntu-24.04`, on the host rather than in the build container, because OpenSearch refuses to run as root. Each job installs its engine with `scripts/install-competitors`, the same script and pins as a local run (see above). The `merge` job combines the reports that finished with `scripts/eval-retrieval-merge`, writes an overall table per engine and class to the job summary, and uploads `eval-competitors` (`competitors-2k.json`, `competitors-needle.json`). A `prepare` job fetches the Loghub inputs once, retrying a failed or mismatched download, and hands them to the engine jobs as an artifact. ck and vecgrep score the 2k seed sets only: on the 100k needle window their multi-line chunk indexes exhaust the hosted runner's 16 GB and the runner shuts down mid-step, so run them on `bgl-needle-100k` locally with enough memory. An engine whose job failed is listed as missing rather than failing the merge. xerj-neural and xerj-semantic are scored three times on both steps (`--quality-repeat 3`, see [Repeated quality runs](#repeated-quality-runs)), and their job timeout is the 360-minute maximum. The needle step times out after 150 minutes, about twice diy-faiss, the slowest engine with one run (about 45 minutes), and after 270 minutes for xerj-neural, whose three runs take about 75 minutes each. The harness prints one progress line per engine phase on stderr (`eval-retrieval: <dataset> <engine>: indexing`, `indexed in N s`, `scored at N s`), so a running job shows which phase it is in. nesso is not built here; nesso's `eval-retrieval` workflow scores it on the same sets. Run it from this repository's Actions with **Run workflow**; it is manual only and never runs on pull requests, because a full run takes over an hour. To check a change to the workflow, run it on the branch with `gh workflow run eval-competitors.yml --ref <branch>`.

Which model each semantic engine uses matters for reading the results. **Same-model controls** use all-MiniLM-L6-v2, the model nesso ships, so a difference comes from the engine, fusion, and routing rather than the model: diy-faiss (fp32, exact search), opensearch-knn (the same vectors, HNSW), and xerj-neural. xerj's neural mode is itself all-MiniLM-L6-v2: without `embedding.local_model_dir` it downloads those three files from Hugging Face. The workflow stages them at the revision diy-faiss pins, so the run is reproducible. xerj's release model bundle is its separate facts model and plays no part in search. **As shipped** engines use their own defaults: vecgrep bundles all-MiniLM-L6-v2, ck uses BAAI/bge-small-en-v1.5, and xerj-semantic is xerj's default `semantic` search, a lexical feature-hashing embedder with no model. A loss to an as-shipped engine can come from its model; that question belongs to a model comparison, not to ranking.

`scripts/eval-retrieval-merge` combines engine reports (`schema_version` 4) or needle reports that cover the same datasets into one report, in input order. It refuses a mix of kinds, different datasets, and an engine that appears twice. Reports from `--measure` merge their `measure` sections too, so each engine can run in its own process on the benchmark machine and still end up in one report: every input must have one (or none may), the CPU model, RAM, `nproc`, platform, repeat count, and `NESSO_THREADS` must match, each measured dataset must have the same log size and line count, a measured engine may appear once, and tool versions are combined (the same tool with two versions is refused). `--markdown` also writes the overall table.

### nesso margin

`scripts/eval-retrieval-compare --current report.json --margins` prints, per system and class, nesso against the best other engine by MRR. It needs no previous report. The headline nesso ranker is `auto`, else the first of `hybrid`, `dense`, `lexical` present. The candidates are the engines scored in the same report plus the reports passed with `--reference` (repeatable). A reference that is a different kind (2k engine report or needle) is ignored, and an engine in the current report wins over the same engine in a reference. The margin is nesso MRR minus the best other MRR, and the table notes classes with fewer than 30 queries, where one query moves MRR by more than 1/30 and small margins are noise. Each row also has a 95% confidence interval for the margin and a verdict. The interval is a paired bootstrap: on the queries both engines answered, the per-query MRR difference is resampled with replacement 5,000 times, and the interval is the 2.5th to 97.5th percentile of the resampled means. The random generator is seeded from the row (system, class, and the two rankers), so a rerun prints the same bounds. The verdict is `win` or `loss` when the interval excludes 0 and `tie` when it contains 0. A reference without per-query results gets `—`. Pairing matters: both engines answer the same queries, so query difficulty cancels out and the interval is much narrower than two independent ones. A `tie` means this query set cannot tell the two apart; it does not mean they are equal. `--margins` and `--previous` can be combined.

The `eval-retrieval` workflow prints this table for the 2k report and the needle report in every run. Its candidates are grep and BM25 from that run, plus the committed reports in `test/eval/reference/` when present, which come from the `eval-competitors` workflow (see that directory's README for the refresh steps).

### Dev and test queries

Every query line can set `"split"` to `dev` (the default) or `test`. `--split dev|test|all` selects which queries are scored (default `all`). Test queries are frozen: `test/eval/test-split.sha256` holds a digest of all of them, and `scripts/check-test-split`, run by `scripts/test`, fails when one changes, so tuning nesso on the test set shows up in review. `scripts/check-test-split --update` rewrites the digest after a deliberate change. A report row for a test query carries `"split":"test"`; dev rows carry no `split`, so existing reports are unchanged. Today each 2k file freezes three queries (its fifth of each class); the sets are small, so a test margin is mostly a tie until they grow.

### Other log shapes

`--dataset all-formats` (or `hadoop-2k`, `openstack-2k`, `healthapp-2k`) scores three more Loghub 2k samples at the same pinned commit: Hadoop (Java log4j with long job, attempt, and container identifiers and exceptions), OpenStack (compute and API lines with request IDs and UUIDs), and HealthApp (pipe-delimited app lines with millisecond timestamps). They are not part of `all-2k`, so results on the six original systems stay comparable. `scripts/fetch-loghub --dataset all-formats` downloads them with the same sha256 checks. Each has 12 queries per class (exact-ID tokens that occur on one to eight lines, all listed as relevant; paraphrases and causes of 12 different events) and its own test events; see `test/eval/README.md`. The scorecard runs them as the `formats` suite.

### Support bundle

A support engineer gets a directory of logs, some rotated, some compressed, some inside archives. `scripts/build-bundle` builds one from six pinned Loghub 2k samples: BGL in a `.tar`, Thunderbird in a `.tgz`, HDFS as a rotated plain file, Apache in a `.zip`, Linux as a plain file, and OpenSSH as a `.gz`, under `var/log/` and `sos_reports/` in `build/bench/bundle/bundle/`. The build is deterministic: gzip, tar, and zip metadata are fixed, and `manifest.json` records each source's decoded sha256, line count, and line offset, in the order nesso visits them (files by byte order of the path). It also writes `SupportBundle_concat.log` (every source's lines in that order, as one file) and a structured CSV with system-prefixed event ids.

`eval-retrieval --dataset support-bundle` scores it. **nesso indexes the bundle directory itself** (`nesso index bundle`, run from the bundle's directory so sources are named as in the manifest), reading every archive in place; its hits (`source`, `line`) are mapped to line ids in the concatenated log through the manifest. **Every other engine reads the concatenated, decoded file**, which is easier for it than the real bundle: an engine that cannot read archives would first need them extracted, and that step is not timed or counted here. So the quality comparison is fair to the others, and nesso's advantage (no extraction step) is not measured yet. `--measure` and `--log-prefix-lines` are refused for this dataset until it is. nesso collapses near-identical lines and reports each occurrence at its own position, so a hit is checked against the manifest (known source, line in range) and not against its text. The scorecard runs it as the quality-only `bundle` suite.

### JSON lines

Loghub has no JSON logs, but a service that logs JSON writes the same events with the fields named. `scripts/derive-json` writes the pinned HDFS_2k sample as one JSON object per line (`ts`, `pid`, `level`, `component`, `message`, with `message` the Loghub `Content` unchanged) as `HDFS_2k_json.jsonl`, beside a copy of the structured CSV. Object n is line n, so the HDFS query set and its labels apply unchanged and any score difference comes from the format. The output is deterministic and its sha256 is pinned in `test/scripts/derive_json_test.py`.

`eval-retrieval --dataset hdfs-2k-json` scores it (`--dataset hdfs-2k,hdfs-2k-json` puts the two side by side); it is not part of `all-2k`. **nesso reads a `.jsonl` file's `message` field by default** (its `--json-field` option names another), reports the object's index as the line number, and prints the field's text. **Every other engine reads the file as text lines**, JSON syntax and field names included, which is what a tool that does not parse JSON sees. This covers one flat schema with the text in `message`. Nested objects, other field names, multi-line records, and JSON arrays are not covered.

### Repeated quality runs

Most engines rank the same way every run, but xerj-neural and xerj-semantic returned different rankings on `bgl-needle-100k` from runs of the same version, so one run is a sample, not their score. `--quality-repeat N` scores every engine other than nesso N times, building its index again each time. The report keeps one real run, the median by overall MRR (the lower median for an even N, then the earlier run), so its per-query rows, which the paired interval uses, all come from the same run. The engine's row gets `quality_repeat`:

- `runs`: N.
- `identical`: `true` when every query's row (ranks and metrics) matched across the runs.
- `changed_queries`: the ids of the queries that differed. In the overall row they are `<dataset>/<id>`.
- `reported_run`: which run (1-based) the row reports.
- `range`: only when something changed, the `[min, max]` of each metric across the runs, for `overall` and for each class in `by_class`.

The text report adds one line per repeated engine row, in the form `# <dataset>/<engine>: 3 quality runs, <n> queries changed, overall MRR <min>-<max>; median run <i> shown`, or `identical rankings` when nothing changed. `eval-retrieval-compare --margins` and `scripts/eval-results-render` mark a ranker whose rankings changed with `†` and a note. The default N is 1, which adds nothing to the report. nesso is not repeated: nesso's own CI checks that its rankings are deterministic. `--quality-repeat` needs quality scoring, so it is refused with `--measure-only` and `--log-prefix-lines`.

### Retrieval eval `--measure`

Off by default. Without it, quality JSON stays byte-identical with prior runs. With `--measure`, the report gains a top-level `measure` object that is machine-dependent and must not be used as a CI or nightly gate.

Numbers (median across `--repeat`, default 3; each engine, and each nesso mode, also has a `range` object with `[min, max]` across the repeats for the timings and peak RSS that have a value, so run-to-run noise is visible next to the median):

| Field | Meaning |
| --- | --- |
| `indexWallSeconds` / `indexPeakRssBytes` | GNU `/usr/bin/time -f "%e %M"` around the index/build child (`nesso index`, FTS5 build, FAISS encode+build, `ck --index` / `vecgrep --index-only`, or spawned xerj or OpenSearch bulk; opensearch-knn also encodes in this child). grep/ripgrep have no index: JSON `null`, tables print `none` (never `0`). |
| `queryWallSeconds` | Wall for the full query set (GNU `%e` of the query child, or the sum of per-query latencies for xerj and OpenSearch so spawn/re-index is not counted). |
| `queryLatencyMedianSeconds` / `queryLatencyP95Seconds` | Median and nearest-rank p95 of per-query latencies inside that child. |
| `queryPeakRssBytes` | Peak RSS of the query-phase child (same GNU time method). |
| `indexBytes` / `indexToLogRatio` | On-disk index size and ratio to the raw log. |
| `timeToFirstResultSeconds` | Cold one-shot: `nesso grep` / `grep` / `rg` on the first query; `ck` / `vecgrep` search a fresh corpus directory and build their index on demand; for indexed engines, index (and spawn for xerj and OpenSearch) plus the first query in one timed child. |

Peak RSS always comes from GNU time on a child process. In-process Python engines (`bm25`, `diy-faiss`) run under `--measure-worker` so RSS is comparable. xerj measure requires a spawned node (`--xerj-bin` / `PATH`), not `--xerj-url`, so the server is inside the timed process tree. OpenSearch measure likewise requires `--opensearch-home` / `OPENSEARCH_HOME`, not `--opensearch-url`; `indexBytes` is the spawned node's data directory after a flush.

Platform, CPU model, total RAM (`memTotalBytes`, from `/proc/meminfo`), `nproc`, `NESSO_THREADS`, and tool versions are recorded in `measure`. Published numbers should come from one fixed machine with those fields kept beside the table.

Larger inputs (speed/memory only, no quality labels):

```bash
python3 scripts/eval-retrieval --measure --log-prefix-lines 100000 \
  --dataset hdfs-v1 --engine nesso --engine grep --engine bm25 \
  --modes dense --repeat 3 --out build/eval/hdfs_100k_measure.json
```

Default `--log-prefix-lines` (when the flag is present without a value) is 100000. The published comparison size is 1000000 lines (the same pin `scripts/fetch-loghub` uses for full sets).

```bash
python3 scripts/eval-retrieval --dataset hdfs-2k \
  --engine nesso --engine grep --engine ripgrep --engine bm25 \
  --measure --repeat 3 --modes dense \
  --out build/eval/hdfs_2k_measure.json
```

The keyword baselines (grep, BM25) also run in the `eval-retrieval` workflow, because they are cheap and their scores do not depend on the runner. The other baselines, and every `--measure` run, stay local or per release: runner timings are too noisy to publish, and the heavy engines download large stacks. Published comparisons should be run on a fixed machine.

Each run of that workflow, including a pull request run, downloads the `eval-retrieval` artifact from the latest successful scheduled run on `main` and runs `scripts/eval-retrieval-compare` on the 2k report and the needle report. A pull request uploads its own reports as `eval-retrieval-pr`, which never becomes the baseline. The compare script prints a Markdown table of per-system, per-ranker, per-class (and overall) recall@10 / MRR / nDCG@10 deltas, plus precision@10 for needle reports. A ranker is a nesso mode or another engine. A nesso-only report (`schema_version` 3) and an engine report (`schema_version` 4) compare with each other, and a needle report compares only with a needle report. The workflow emits a warning annotation when a score drops by more than 5% relative to the previous value (`--tolerance` or `NESSO_EVAL_TOLERANCE`). A missing previous artifact prints `no previous run to compare`. Scores never fail the job; only unreadable or malformed JSON does.

When both reports carry per-query results, the compare also prints an **MRR change by query** section. It has one row per system, ranker, and class (and overall) where at least one query's MRR changed or the query set changed. Each row gives the mean per-query change, a 95% interval, and a verdict. The interval is the paired bootstrap described under [nesso margin](#nesso-margin), here on current minus previous MRR for the queries both runs scored. The verdict is `better` or `worse` when the interval excludes 0, and `within noise` when it contains 0. A list of the queries whose MRR changed follows, largest change first, capped at 30. For needle reports each entry also shows the first-hit rank before and after. On a class of 17 queries, one query that falls from rank 1 to rank 14 lowers the class MRR by about 0.055, more than the 5% tolerance, and the row still reads `within noise`. When the two runs scored different queries in a class, for example after the query sets grew, the class score moves with the query set. That row and the class's MRR `DROP` line then say `query set changed: S shared of C current, P previous` and give no interval or verdict; n and change count the shared queries. Otherwise an MRR `DROP` line carries the same interval and verdict, so the workflow's warning says whether the drop is noise.

### Speed and memory on the needle windows

`--measure` on a needle dataset times every engine on the window's log and the window's queries, with the same columns and method as the 2k measure above (GNU `time` around each phase's child process): index wall and peak RSS, index size and ratio to the raw log, query wall, p50 and p95, query peak RSS, and cold time to first result. That puts quality, memory, and speed on the same task and at 100,000 and 1,000,000 lines, where the 2k samples cannot show the differences.

```bash
python3 scripts/eval-retrieval --dataset bgl-needle-100k \
  --engine nesso --engine grep --engine bm25 --modes auto,dense \
  --measure --repeat 3 --out build/eval/needle_bgl_100k_measure.json
```

`--measure-only` skips the quality scoring and only measures, which saves the second pass over a slow engine. Quality and measurements share one report: the measurements are under `measure` and the scores under `datasets`. Run `--repeat 1` at 1,000,000 lines. `xerj` and OpenSearch run in a spawned node per phase, so their peak RSS includes the server, and `--xerj-url` and `--opensearch-url` are refused. The report records the machine, the tool versions, and, for nesso, a digest of `model.onnx` and `vocab.txt` (`measure.tool["nesso-model"]` and the top-level `nesso.model`), so numbers produced with a different embedding model, quantization, or vocabulary cannot be mistaken for each other. Timings from a laptop are for development. Published numbers should come from one fixed machine, with the platform fields kept beside the table, and are never produced by CI.

### Scorecard run

`scripts/scorecard --nesso-version VERSION` runs the whole comparison on the benchmark machine with one command, so every release is measured the same way. It writes to `results/<VERSION>/` (`--out` to change it); indexes and temporary corpora go to `build/scorecard/`.

1. **Preflight.** It refuses WSL, a 1-minute load average above 1.0, and a nesso-bench checkout with uncommitted changes. `--dev` allows them and marks the run development-only. `machine.json` records the CPU model, `nproc`, RAM, swap, kernel and OS, CPU governor, SMT, CPU vulnerability mitigations, free disk, `lscpu`, the versions of Python, GNU time, grep, and SQLite, the nesso-bench commit, the memory cap, and the timeout. It also records which nesso was scored: `nessoVersion`, `nessoSource` (`release` or `binary`), `nessoVersionOutput` (what `nesso -V` printed), `nessoBinary` and `nessoBinarySha256`, and `nessoModel` (the same model identity eval-retrieval reports carry: the model directory's name and the sha256 and size of `model.onnx` and `vocab.txt`; `nessoFp32Model` too for an fp32 run). `developmentOnly` is true when anything made the run development-only, and `developmentReasons` lists why.
2. **Setup.** `scripts/install-nesso VERSION` installs the released nesso and its shipped model (or, with `--nesso-binary`, nothing is installed for nesso; see below); `scripts/install-competitors` installs the competitors the selected groups need. ck's model is downloaded once before anything is timed. `scripts/fetch-loghub` fetches every input the selected suites need.
3. **Runs.** Each suite and engine group is one `scripts/eval-retrieval --measure` process, wrapped in `systemd-run --user --scope -p MemoryMax=<cap> -p MemorySwapMax=0` (default cap 48G, `--memory-max none` to run uncapped) and `timeout` (default 8 hours, `--timeout-hours`). An engine that runs out of memory or time is recorded as that outcome, and the other runs continue. Out-of-memory is decided from systemd's verdict on the run's scope (`Result=oom-kill`, read once the scope has settled), because the kernel kills one process and systemd then stops the rest with SIGTERM, so the run's exit code is -15 or 143 and `timeout` may even report 124. The exit code and the harness's `exit -9` are the fallback. nesso runs with grep, so its report has the engine layout the merge needs. Each run's output is `raw/<suite>/<group>.log`.
4. **Merge.** Each suite's finished reports are merged into `merged/<suite>.json` with `scripts/eval-retrieval-merge`. `status.json` lists every run with its outcome (`ok`, `timeout`, `out-of-memory (<cap>)`, or `failed (exit N)`), exit code, and wall time, and every merge.

| Suite | Dataset | Repeats | Scores |
| --- | --- | --- | --- |
| `2k` | the six Loghub 2k samples | 3 | quality, speed, memory |
| `formats` | the Hadoop, OpenStack, and HealthApp 2k samples (see below) | 3 | quality, speed, memory |
| `json` | HDFS_2k as JSON lines (see JSON lines) | 3 | quality, speed, memory |
| `bundle` | the support bundle (see Support bundle) | none | quality only: `--measure` is refused for it |
| `bgl-needle-100k` | BGL needle window, 100,000 lines | 3 | quality, speed, memory |
| `bgl-needle-1m` | BGL needle window, 1,000,000 lines | 1 | quality, speed, memory |
| `thunderbird-needle-1m` | Thunderbird needle window, 1,000,000 lines | 1 | quality, speed, memory |
| `full-1m` | first 1,000,000 lines of HDFS_v1, BGL, and Thunderbird | 1 | speed and memory only |

The engine groups are `nesso` (nesso in `auto`, `dense`, and `lexical`, with grep), `ripgrep`, `bm25`, `diy-faiss`, `opensearch`, `opensearch-knn`, `xerj`, `xerj-neural`, `xerj-semantic`, `ck`, and `vecgrep`. `xerj-neural` and `xerj-semantic` also pass `--quality-repeat` with the suite's repeat count (3 on `2k` and `bgl-needle-100k`; one run on the 1,000,000-line suites), so their scores carry the spread across runs. On `bgl-needle-100k` that makes six index builds for xerj-neural, three for quality and three for `--measure`, which is the run closest to the default 8-hour timeout. `--suites` and `--groups` select a subset. `--nesso-threads-1` adds the `nesso` group again at `NESSO_THREADS=1`, and `--nesso-fp32` adds nesso alone with the fp32 model (`install-nesso --fp32`, as `raw/<suite>/nesso-fp32.json`). Neither report is merged, because the thread setting and the model are part of a report's setting. `--dry-run` prints the planned runs as JSON lines, each with the nesso version (or binary and model directory) it would score.

**Scoring a nesso built from a commit.** `--nesso-binary PATH --nesso-model-dir DIR` replaces `--nesso-version`: exactly one of the two is required, and the binary needs its model directory (`model.onnx` and `vocab.txt`). This is how `main` or a release candidate is measured, for example from a nesso workflow artifact. Nothing is downloaded for nesso: every nesso run gets the binary and model directory the way `install-nesso` exports them (`NESSO_BINARY`, `NESSO_MODEL_DIR`, and the binary's directory on `PATH`). The scorecard runs `<binary> -V` (a build from a commit prints, for example, `0.3.1+gb20ff665cbb6`), and the default `--out` is `results/<-V output>`, with characters that are unsafe in a path replaced by `_`. Such a run is development-only, as with `--dev`, unless the `-V` output is exactly a version `install-nesso` pins; `nessoSource` stays `binary` either way, so the binary's sha256 can be checked against the release. `--nesso-fp32` with a binary needs `--nesso-fp32-model-dir DIR` and is refused without it; the fp32 model is not downloaded for a binary.

```bash
scripts/scorecard --nesso-version 0.3.1 --dry-run | wc -l
scripts/scorecard --nesso-version 0.3.1 --nesso-threads-1 --nesso-fp32
# Development smoke on a laptop: small suites, marked development-only.
scripts/scorecard --nesso-version 0.3.1 --suites 2k --groups nesso,bm25 --memory-max 4G --dev
# A nesso built from a commit, with its model: development-only, results in results/<nesso -V>/.
scripts/scorecard --nesso-binary ../nesso/build/Release/src/nesso --nesso-model-dir ../nesso/models --suites json --groups nesso --dev
```

The full run takes many hours: the embedding engines index the 1,000,000-line windows slowly, and ck and vecgrep may hit the memory cap there. That outcome is a result to report, not a failure of the run.

### Checking the memory cap, and the CI smoke run

The scorecard runs every engine under `systemd-run --user --scope -p MemoryMax=...`, so an engine that runs out of memory is killed and recorded as that outcome. That needs a systemd user manager with the memory controller, which a headless SSH or CI session often lacks. `scripts/check-memory-cap` checks it with a bounded probe (a 400 MB allocation under a 100 MB cap; the cap works if the probe is killed). When there is no user manager it enables lingering and starts `user@UID.service` once, probes again, and prints (or, with `--env-file`, appends in the `GITHUB_ENV` format) `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS`. It exits 1 with an explanation when the cap still does not work. Run it first on any new machine. `--memory-max none` runs uncapped, and a runaway engine then takes the machine down.

`scripts/scorecard-status results/<VERSION> [more directories]` prints the machine and the nesso each directory scored (`(binary)` when it was not a pinned release), a table of engine group by suite with each run's outcome and wall time, and lists every run that did not finish, so a long run can be read at a glance. A group that ran in more than one directory, such as nesso main and its release baseline, gets one row per directory, labelled with the directory name.

`scripts/scorecard-ratios --keywords DIR NAME=DIR [NAME=DIR ...]` prints nesso's timings as ratios to keyword engines timed on the same runner, per measured suite and nesso build: index ÷ bm25 (index wall times summed over the datasets both finished), and query p50 ÷ grep and ÷ ripgrep (the median of the per-dataset ratios, nesso mode `auto` unless `--mode`). grep comes from each nesso report; bm25 and ripgrep from the `--keywords` directory. The table is labelled development-only and lists the CPU each report recorded, with a warning when they differ, because a ratio across runners compares two machines.

The **Scorecard smoke** workflow (`.github/workflows/scorecard-smoke.yml`) runs the scorecard on GitHub-hosted runners, weekly (Sunday 16:23 UTC) and on `workflow_dispatch`. It checks that the pipeline works on real Linux, and puts nesso main next to the last release. It checks the memory cap first (every scoring job needs it). The `nesso-main` job finds the nesso build to score as main: the latest successful scheduled run of nesso's Package workflow on `main` (or the run given as `nesso_run_id`), records its run id and head SHA, downloads its `repro-deb-amd64-a` artifact with the job's own token (`actions: read`; nesso is public), checks that the `.deb` holds `/usr/bin/nesso` and `/usr/share/nesso/{model.onnx,vocab.txt}`, and passes it on. Package artifacts expire after 14 days, so the job fails when the run is older than that. The `score-nesso` job then runs, on one runner, `scripts/scorecard --nesso-version <nesso_version>` (default 0.3.1) with nesso and the keyword engines ripgrep, bm25, opensearch, and xerj, and `scripts/scorecard --nesso-binary … --nesso-model-dir …` on the unpacked `.deb` (`dpkg-deb -x`, not installed) with nesso alone, on `2k,formats,json,bundle,bgl-needle-100k`, each with its own `--out`. The keyword engines run once, next to the baseline: they do not depend on the nesso build, and every suite they ran on before is in that job. Every embedding engine group (diy-faiss, opensearch-knn, xerj-neural, xerj-semantic, ck, vecgrep) runs in its own job on `2k,formats,json,bundle` (xerj-semantic also on `bgl-needle-100k`; ck and vecgrep exhaust the 16 GB runner on that window, and the other embedding engines take one to two hours there). Every scorecard runs with `--dev --repeat 1 --memory-max 12G`. A separate `oom` job runs vecgrep on `bgl-needle-100k` under a 3 GB cap and asserts that the scorecard records `out-of-memory (3G)` and carries on. Each job uploads its results folder (`scorecard-smoke-<group>`, and `scorecard-smoke-nesso-baseline` and `scorecard-smoke-nesso-main` from the nesso job; the main folder has `nesso-package.json` with the Package run id, head SHA, and `.deb` sha256). The final job writes to its summary: every group in one table (`scripts/scorecard-status`); the Package run and SHA scored as main; quality of main against the baseline per suite, system, ranker, and class (`scripts/eval-retrieval-compare` on the two `nesso.json` reports, with the per-query paired intervals where the reports have per-query results); and, from the nesso job only, `scripts/scorecard-ratios`: nesso index wall ÷ bm25 and nesso query p50 ÷ grep and ÷ ripgrep, for main and the baseline. Everything is development-only: hosted runners are shared and noisy, so no number from it is published, and the ratios are only meaningful because each pair shared a runner. Dispatch it with `gh workflow run scorecard-smoke.yml --ref <branch>` (`-f nesso_version=X.Y.Z` and `-f nesso_run_id=N` pick other builds). `scripts/scorecard --repeat N` sets the repeat count of every measured suite for runs like this one. Artifacts expire after 14 days, so a run worth keeping is copied into `results/ci-smoke/<date>/` with a README that labels it development-only; [`results/ci-smoke/2026-11-21/`](../results/ci-smoke/2026-11-21/README.md) is the first one, the only run so far that timed every engine group, each on its own runner.

### Rendering the scorecard

`scripts/eval-results-render results/<VERSION>` turns a `scripts/scorecard` results directory into one Markdown page, `docs/results/<VERSION>.md` by default (`--out` to change it). The page has, in order:

- **Machine:** the fields from `machine.json`, including the nesso `-V` output, binary sha256, and model digest, and a development-only banner, with `developmentReasons`, when the run used `--dev` or scored a binary that is not a pinned release.
- **Where nesso loses:** every row, per system and pooled, where another ranker or nesso mode beats nesso's headline mode (`auto`) on the same queries with its whole 95% interval below 0. It uses the same paired bootstrap as `eval-retrieval-compare --margins`.
- **Quality:** per suite, the pooled rows per ranker and class: MRR, nDCG@10, recall@10 (p@10 on needle suites), nesso `auto` minus the ranker with its 95% interval, and the verdict from nesso's side.
- **int8 against fp32:** when the run used `--nesso-fp32`, per suite and per nesso mode and class: MRR with the shipped int8 model and with the fp32 one, int8 minus fp32 with its 95% paired interval, and the verdict from int8's side. A `loss` is quality the quantization costs.
- **Speed and memory:** per measured dataset: index lines/s, index wall, index peak RSS, index size and its ratio to the log, query p50 and p95, query peak RSS, and time to first result. Medians, with (min–max) when the repeats differ. The `NESSO_THREADS=1` and fp32 reports follow when present.
- **Runs that did not finish:** each run whose outcome was not `ok`, such as `out-of-memory (48G)`.
- **Versions:** the tool versions the measured reports recorded.

The page is deterministic for a given results directory, so a rerender shows as a real diff.
