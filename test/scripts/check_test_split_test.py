import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check-test-split"
EVAL = ROOT / "scripts" / "eval-retrieval"


def check(root: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *args], capture_output=True, text=True, check=False)


def copy_queries(directory: pathlib.Path) -> pathlib.Path:
    shutil.copytree(ROOT / "test" / "eval", directory / "test" / "eval")
    return directory


class CheckTestSplitTest(unittest.TestCase):
    def test_committed_digest_matches(self) -> None:
        # The check CI relies on: the repository's test queries are the frozen ones.
        completed = check(ROOT)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertRegex(completed.stdout, r"ok: \d+ test queries match")

    def test_every_2k_file_has_a_test_query_per_class(self) -> None:
        for path in sorted((ROOT / "test" / "eval" / "queries").glob("*_2k.jsonl")):
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("{")]
            test = {row["class"] for row in rows if row.get("split") == "test"}
            self.assertEqual(test, {"exact_id", "paraphrase", "cause"}, path.name)
            # Dev queries remain in every class, so there is something to tune on.
            self.assertEqual({row["class"] for row in rows if row.get("split", "dev") == "dev"}, {"exact_id", "paraphrase", "cause"}, path.name)

    def test_changes_to_a_test_query_fail_until_updated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = copy_queries(pathlib.Path(temp))
            self.assertEqual(check(root).returncode, 0)
            path = root / "test" / "eval" / "queries" / "hdfs_2k.jsonl"
            original = path.read_text(encoding="utf-8")
            # Editing a test query's text.
            target = next(line for line in original.splitlines() if line.startswith("{") and '"split":"test"' in line and '"cause"' in line)
            edited = original.replace(target, target.replace('"query":"', '"query":"edited '))
            self.assertNotEqual(edited, original)
            path.write_text(edited, encoding="utf-8")
            failed = check(root)
            self.assertEqual(failed.returncode, 1)
            self.assertIn("test queries changed", failed.stderr)
            # Moving a test query to dev is also a change.
            path.write_text(original.replace(',"split":"test"', "", 1), encoding="utf-8")
            self.assertEqual(check(root).returncode, 1)
            # A reviewed change is made visible by --update.
            self.assertEqual(check(root, "--update").returncode, 0)
            self.assertEqual(check(root).returncode, 0)

    def test_dev_queries_are_free_to_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = copy_queries(pathlib.Path(temp))
            path = root / "test" / "eval" / "queries" / "hdfs_2k.jsonl"
            text = path.read_text(encoding="utf-8")
            dev = next(line for line in text.splitlines() if line.startswith("{") and '"split"' not in line and '"cause"' in line)
            path.write_text(text.replace(dev, dev.replace('"query":"', '"query":"edited ')), encoding="utf-8")
            self.assertEqual(check(root).returncode, 0)

    def test_missing_digest_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = copy_queries(pathlib.Path(temp))
            (root / "test" / "eval" / "test-split.sha256").unlink()
            failed = check(root)
        self.assertEqual(failed.returncode, 1)
        self.assertIn("--update", failed.stderr)


class SplitOptionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import importlib.machinery
        import importlib.util

        loader = importlib.machinery.SourceFileLoader("eval_retrieval_split", str(EVAL))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        assert spec is not None
        cls.mod = importlib.util.module_from_spec(spec)
        sys.modules[loader.name] = cls.mod
        loader.exec_module(cls.mod)

    def test_loader_reads_the_split(self) -> None:
        queries = self.mod.load_queries(ROOT / "test" / "eval" / "queries" / "hdfs_2k.jsonl")
        tests = {query.id for query in queries if query.split == "test"}
        # The first generation of frozen queries stays frozen.
        self.assertLessEqual({"cause_05", "exact_05", "para_05"}, tests)
        self.assertGreater(sum(query.split == "dev" for query in queries), len(tests) // 2)

    def test_select_split(self) -> None:
        path = ROOT / "test" / "eval" / "queries" / "hdfs_2k.jsonl"
        queries = self.mod.load_queries(path)
        tests = sum(query.split == "test" for query in queries)
        self.assertEqual(len(self.mod.select_split(queries, "all", path)), len(queries))
        self.assertEqual(len(self.mod.select_split(queries, "dev", path)), len(queries) - tests)
        self.assertEqual(len(self.mod.select_split(queries, "test", path)), tests)
        with self.assertRaises(SystemExit):
            self.mod.select_split([query for query in queries if query.split == "dev"], "test", path)

    def test_bad_split_value_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "q.jsonl"
            path.write_text('{"id":"a","class":"exact_id","query":"x","relevant_lines":[1],"split":"holdout"}\n', encoding="utf-8")
            with self.assertRaises(SystemExit) as raised:
                self.mod.load_queries(path)
        self.assertIn("split must be one of", str(raised.exception))

    def test_rows_label_test_queries_only(self) -> None:
        mod = self.mod
        queries = [
            mod.Query("d", "exact_id", "a", frozenset({1}), None),
            mod.Query("t", "exact_id", "b", frozenset({2}), None, "test"),
        ]
        scored = mod.score_queries(queries=queries, event_by_line={}, rank_fn=lambda q: [1, 2])
        rows = {row["id"]: row for row in scored["queries"]}
        self.assertNotIn("split", rows["d"])
        self.assertEqual(rows["t"]["split"], "test")

    def test_needle_loader_and_rows(self) -> None:
        mod = self.mod
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "n.jsonl"
            path.write_text(
                '{"id":"a_kw","class":"keyword","alert":"A","query":"x"}\n'
                '{"id":"b_kw","class":"keyword","alert":"B","query":"y","split":"test"}\n',
                encoding="utf-8",
            )
            queries = mod.load_needle_queries(path)
            self.assertEqual([query.split for query in queries], ["dev", "test"])
            self.assertEqual([query.id for query in mod.select_split(queries, "test", path)], ["b_kw"])
            row = mod.needle_query_row(queries[1], frozenset({1}), [1], 1.0)
            self.assertEqual(row["split"], "test")
            self.assertNotIn("split", mod.needle_query_row(queries[0], frozenset({1}), [1], 1.0))

    def test_cli_scores_one_split(self) -> None:
        queries = self.mod.load_queries(ROOT / "test" / "eval" / "queries" / "hdfs_2k.jsonl")
        tests = sum(query.split == "test" for query in queries)
        for split, expected in (("dev", len(queries) - tests), ("test", tests), ("all", len(queries))):
            with tempfile.TemporaryDirectory() as temp:
                out = pathlib.Path(temp) / "out.json"
                done = subprocess.run(
                    [sys.executable, str(EVAL), "--dataset", "hdfs-2k", "--engine", "grep", "--split", split, "--skip-fetch",
                     "--workdir", str(pathlib.Path(temp) / "w"), "--out", str(out)],
                    capture_output=True, text=True, check=False,
                )
                if not (ROOT / "build" / "bench" / "HDFS_2k.log").is_file():
                    self.skipTest("Loghub 2k inputs not fetched")
                self.assertEqual(done.returncode, 0, done.stderr)
                report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["datasets"][0]["query_count"], expected, split)


if __name__ == "__main__":
    unittest.main()
