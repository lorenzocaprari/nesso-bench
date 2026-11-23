# Method and limits

What these results can and cannot show, and the rules that keep them honest. The how-to
for each tool is in [eval.md](eval.md).

## Rules

1. **Tune on dev, report on test.** A query line has a `split`, `dev` (the default) or `test`.
   Change nesso's ranking while looking at dev queries only (`eval-retrieval --split dev`).
   Test queries are frozen: `test/eval/test-split.sha256` holds a digest of all of them, and
   `scripts/test` fails when one is edited, moved, added, or dropped. A deliberate change goes
   through `scripts/check-test-split --update` and the commit message says why. Do not read
   test results while changing the ranking.
2. **Queries are fixed before scoring.** Do not add, reword, or relabel a query after seeing
   where nesso loses; that fits the benchmark to the product. A new query set is written and
   reviewed before it is scored, and a query that turns out to be wrong is removed for every
   engine, with the reason in the commit.
3. **Losses are published.** The rendered scorecard lists every row where another ranker beats
   nesso's headline mode with a 95% interval entirely below zero (`eval-results-render`,
   "Where nesso loses"), per system and pooled. An engine that cannot finish a task under the
   memory cap or the time limit is listed as that outcome, not dropped.
4. **A tie is a tie.** The margin carries a paired bootstrap interval. `win` or `loss` means the
   interval excludes zero; `tie` means this query set cannot tell the two apart, not that
   they are equal. Claims in text must match the verdict column.
5. **Everyone gets the same inputs.** Same logs, same queries, same k, same machine. Tools and
   models are pinned by version or commit and checked by checksum; setups are in
   [eval.md](eval.md). Where an engine runs as shipped with its own model, the page says so,
   because a loss there can come from the model and not the ranking.
6. **Numbers carry their provenance.** Published quality and speed come from the released nesso
   binary (`install-nesso`) on one fixed machine, never from a laptop or a hosted runner, with the
   machine, tool versions, and model digests recorded beside them.
7. **Nondeterminism is shown, not hidden.** An engine whose rankings change between runs is
   scored several times (`--quality-repeat`); the report keeps the median run and the spread,
   and the page marks it.
8. **Held-out systems are scored only at release, never while tuning.** Seven Loghub 2k systems
   that the dev and test sets do not touch (Spark, Zookeeper, HPC, Windows, Mac, Android, and
   Proxifier; `--dataset all-heldout`) carry `"split":"heldout"` on every query. Test queries
   share their nine systems with the dev queries nesso is tuned on, so they cannot show whether
   ranking rules fitted to those systems carry over to logs nesso has never seen; the held-out
   group can. It is scored with `eval-retrieval --dataset all-heldout --split heldout` when a
   release is measured, and at no other time: not during tuning, not to pick between two ranking
   changes, and not to debug a loss. The default (`all`) and `dev` runs never include it, and
   `eval-retrieval` refuses a held-out dataset without `--split heldout`. Its queries were written
   from the logs and Loghub's templates without running nesso, and they are frozen like the test
   queries: `test/eval/heldout-split.sha256` holds their digest and `scripts/check-test-split`
   fails on any edit. Once a release result on them is read, ranking changes that follow are
   informed by it, so a large change after that should be checked on a new held-out group.

## Limits

- **Who wrote the queries.** The Loghub 2k query sets and their phrasings were written by the
  nesso project. Exact-ID labels are checked against the log (a listed line exists and contains the
  identifier as a whole token), and event labels are Loghub's own template assignments from the
  structured CSV, but the choice of what to ask is ours. The needle windows are different: relevance is the alert category the system
  administrators tagged, not our judgement. Independent review or additional queries from
  outside the project would make the quality claims stronger, and would be stated here.
- **Small sets and correlated queries.** Most classes have few queries, so many margins are ties.
  Queries on the same event or alert are not independent evidence, and the pooled interval treats
  them as if they were, so it is narrower than it should be for datasets with few templates
  (HDFS_2k has 14).
- **Public data.** Loghub logs are public, and the embedding models in several engines were
  probably trained on text like them. That affects every engine that uses a model, not only nesso.
- **Log shapes covered.** The sets are single-line plain-text logs: three in syslog format
  (Linux, OpenSSH, Thunderbird), HDFS, BGL, and Apache error logs, and, as a separate group,
  Java log4j lines with long identifiers and exceptions (Hadoop), request-id API and compute
  lines (OpenStack), and pipe-delimited app lines (HealthApp). The held-out group (rule 8) adds
  Spark executor and Zookeeper log4j lines, HPC cluster event records, Windows CBS servicing
  logs, macOS syslog, Android logcat, and Proxifier connection lines. One small dataset, the support
  bundle, puts six of the first group in a directory with `.gz`, `.tar`, `.tgz`, and `.zip`
  files; it scores quality only, and the other engines read it decoded, so it does not show
  nesso's advantage of skipping extraction. Loghub has no JSON logs, so the one JSON dataset
  is HDFS_2k rewritten by us as flat JSON lines with a `message` field, with the same labels;
  nested objects and other schemas are not covered. Multi-line records such as stack traces,
  and container and journald output, are not covered either. Results say nothing about these
  shapes.
- **One machine type.** Speed and memory hold for the machine in `machine.json`. Other CPUs,
  memory sizes, and disks will differ; the run-to-run spread on that machine is measured and
  published before any regression threshold is set from it.
- **Fixed settings.** Competitors run at their defaults, with the exceptions listed in
  [eval.md](eval.md). A tuned deployment of another tool could do better than the default one
  measured here.
- **Versions age.** Results describe the versions listed on the page. Competitor releases change;
  a result is not a claim about a later version.

## Reproducing a result

`scripts/scorecard --nesso-version VERSION` runs the whole comparison on one machine and writes
raw reports, `machine.json`, and `status.json`; `scripts/eval-results-render` turns them into the
page. Every download is checked against a pin in the repository. Anyone can rerun it, and a
difference of more than the measured run-to-run spread is worth reporting as an issue.
