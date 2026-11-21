# Retrieval evaluation seeds

`queries/*_2k.jsonl` are **seed** query sets for `scripts/eval-retrieval`. Each file
has about five queries in each class (`exact_id`, `paraphrase`, `cause`) against one
pinned Loghub 2k sample (HDFS, BGL, Thunderbird, OpenSSH, Linux, Apache).

A query sets exactly one of `relevant_lines` (1-based LineIds) or `relevant_events`
(Loghub EventIds from the matching `*_2k.log_structured.csv`). Exact-ID seeds use
`relevant_lines`. Paraphrase and cause seeds use `relevant_events`. The script
rejects both, neither, the old `relevant` key, a duplicate id, and an event that does not occur in the structured CSV. Each listed line must exist in
the log and contain the query as a whole token (`blk_123` does not match inside
`blk_1234`). The structured CSV row count must equal the log line count so LineId
matches nesso's 1-based lines, including a final line with no trailing newline.

The relevant set R is those lines, or every line whose EventId is listed. Scores
use binary gains on lines:

- recall@10 = |top 10 ∩ R| / min(10, |R|)
- MRR = 1 / rank of the first line in R (0 if none)
- nDCG@10 = DCG@10 / IDCG of min(10, |R|) relevant lines

## Dev and test queries

A query line may set `"split":"dev"` (the default) or `"split":"test"`. Tune nesso
on the dev queries (`eval-retrieval --split dev`) and keep the test queries for
reporting (`--split test`; the default `all` scores both). Test queries are
frozen: the digest of every one is committed in `test-split.sha256`, and
`scripts/check-test-split` (run by `scripts/test`) fails when one is edited, moved,
added, or dropped. A deliberate change is made visible with
`scripts/check-test-split --update`, and the commit message says why. A report row
for a test query carries `"split":"test"`. Each 2k file freezes its `*_05` query of
each class; needle files can use the same field.

HDFS_2k has only 14 event templates, and four of them cover about 300 lines or
more, so its paraphrase and cause queries are written two per event (ten events).
Queries on the same event are not independent evidence, and the pooled interval
treats them as if they were. The events E6, E8, and E13 are the test events: both
phrasings of each are in the frozen split, so no test event is also tuned on.

Linux_2k has 118 templates, so its 20 new paraphrase and cause queries each use a
different event, one phrasing per class (E36, E89, E4, E107, E46, and E88 are the
test events). Its exact-ID queries are PIDs, IP addresses, and other tokens that
occur on exactly one line.

OpenSSH_2k has 27 templates, and several of them differ only in the account or the
reason (the PAM failure variants), which a query cannot tell apart, so those are left
out. Its 20 new paraphrase and cause queries cover 16 events; E24, E9, E2, and E5 have
two phrasings each, so those are not independent. E8, E14, E11, E26, and E2 are the test
events. Its exact-ID queries are ports (one line each), IP addresses, and user names
that occur on 2 to 8 lines, all of which are listed as relevant.

These seed sets are for local development and CI-free smoke scoring. They are
**not** the published retrieval benchmark; the full public set comes later from
Product.

```bash
./scripts/fetch-loghub --dataset all-2k
python3 scripts/eval-retrieval --dataset all-2k --out build/eval/all_2k.json
```

Keyword baselines (`--engine grep`, `ripgrep`, `bm25`), the optional DIY semantic baseline (`--engine diy-faiss`), the optional XERJ baselines (`--engine xerj`, `xerj-neural`), the optional OpenSearch baselines (`--engine opensearch`, `opensearch-knn`), and the semantic-grep CLIs (`--engine ck`, `vecgrep`) reuse these seeds and the same line metrics. See [docs/eval.md](../../docs/eval.md) for setup, fairness notes, and query rules. Those paths are local or per-release, not Pipeline or nightly.

`needles/*.jsonl` are the needle benchmark queries: one `keyword` and one `symptom` query per alert category, with no relevance labels in the file. Relevance comes from the administrators' alert tags in the Loghub 2.0 windows that `scripts/fetch-loghub --window` writes. See [docs/eval.md](../../docs/eval.md#needle-benchmark).
