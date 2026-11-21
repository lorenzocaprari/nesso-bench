import csv
import hashlib
import importlib.machinery
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
DERIVE = ROOT / "scripts" / "derive-json"
EVAL = ROOT / "scripts" / "eval-retrieval"
# sha256 of the derived file from the pinned HDFS_2k sample. A change to the
# transformation, deliberate or not, changes it.
PINNED_SHA256 = "90080bcb2ff0848783681a79978530bcbfe33478adcea678b31d2f577dab60d5"


def load(path: pathlib.Path, name: str):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def write_structured(directory: pathlib.Path, rows: list[dict[str, str]]) -> None:
    fields = ["LineId", "Date", "Time", "Pid", "Level", "Component", "Content", "EventId", "EventTemplate"]
    with (directory / "HDFS_2k.log_structured.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


ROW = {
    "LineId": "1",
    "Date": "081109",
    "Time": "203615",
    "Pid": "148",
    "Level": "INFO",
    "Component": "dfs.DataNode$PacketResponder",
    "Content": 'PacketResponder 1 for block blk_1 "terminating"',
    "EventId": "E10",
    "EventTemplate": "t",
}


class DeriveJsonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load(DERIVE, "derive_json")

    def test_one_object_per_line_with_the_content_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = pathlib.Path(temp)
            write_structured(directory, [ROW, {**ROW, "LineId": "2", "Date": "081110", "Time": "000001", "Content": "naïve ünï"}])
            out = directory / "out"
            self.assertEqual(self.mod.derive(out, directory), 2)
            text = (out / "HDFS_2k_json.jsonl").read_text(encoding="utf-8")
            copied = (out / "HDFS_2k_json.jsonl_structured.csv").read_bytes()
            original = (directory / "HDFS_2k.log_structured.csv").read_bytes()
        first, second = (json.loads(line) for line in text.splitlines())
        self.assertEqual(
            first,
            {"ts": "2008-11-09T20:36:15", "pid": 148, "level": "INFO", "component": "dfs.DataNode$PacketResponder", "message": ROW["Content"]},
        )
        self.assertEqual(list(first), ["ts", "pid", "level", "component", "message"])
        self.assertEqual(second["ts"], "2008-11-10T00:00:01")
        self.assertEqual(second["message"], "naïve ünï")
        self.assertEqual(len(text.splitlines()), 2)
        # The labels are the original's: line n of the JSON is line n of the log.
        self.assertEqual(copied, original)

    def test_bad_input_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = pathlib.Path(temp)
            with self.assertRaises(SystemExit) as missing:
                self.mod.derive(directory / "out", directory)
            self.assertIn("fetch-loghub", str(missing.exception))
            write_structured(directory, [{**ROW, "LineId": "2"}])
            with self.assertRaises(SystemExit) as gap:
                self.mod.derive(directory / "out", directory)
            self.assertIn("LineId 2 at row 1", str(gap.exception))
            write_structured(directory, [{**ROW, "Date": "0811"}])
            with self.assertRaises(SystemExit) as date:
                self.mod.derive(directory / "out", directory)
            self.assertIn("unexpected HDFS date/time", str(date.exception))

    def test_pinned_output_of_the_real_sample(self) -> None:
        if not (self.mod.BENCH_DIR / "HDFS_2k.log_structured.csv").is_file():
            self.skipTest("HDFS_2k not fetched")
        with tempfile.TemporaryDirectory() as temp:
            self.mod.derive(pathlib.Path(temp))
            digest = hashlib.sha256((pathlib.Path(temp) / "HDFS_2k_json.jsonl").read_bytes()).hexdigest()
        self.assertEqual(digest, PINNED_SHA256)


class EncodedDatasetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load(EVAL, "eval_retrieval_json")

    def test_selected_by_name_only_and_reuses_the_hdfs_queries(self) -> None:
        mod = self.mod
        spec = mod.parse_datasets("hdfs-2k-json")[0]
        self.assertEqual(spec.name, "hdfs-2k-json")
        self.assertEqual(spec.queries_path, mod.DATASETS_2K["hdfs-2k"].queries_path)
        # all-2k and all-formats keep their systems, so existing results stay comparable.
        self.assertNotIn("hdfs-2k-json", [item.name for item in mod.parse_datasets("all-2k")])
        self.assertNotIn("hdfs-2k-json", [item.name for item in mod.parse_datasets("all-formats")])
        both = mod.parse_datasets("hdfs-2k,hdfs-2k-json")
        self.assertEqual([item.name for item in both], ["hdfs-2k", "hdfs-2k-json"])
        self.assertTrue(spec.corpus_name.endswith(".nesso"))

    def test_the_hdfs_labels_validate_against_the_json_lines(self) -> None:
        mod = self.mod
        spec = mod.DATASETS_ENCODED["hdfs-2k-json"]
        if not (spec.log_path.is_file() and spec.structured_path.is_file()):
            self.skipTest("hdfs-2k-json not derived")
        queries = mod.load_queries(spec.queries_path)
        lines = mod.read_log_lines(spec.log_path)
        events = mod.load_event_ids(spec.structured_path)
        mod.assert_line_id_alignment(spec.log_path, events, lines)
        mod.validate_relevant_lines(queries, spec.log_path, lines)
        mod.validate_relevant_events(queries, events, spec.structured_path)
        self.assertTrue(lines[0].startswith('{"ts":"2008-11-09T20:36:15"'))


if __name__ == "__main__":
    unittest.main()
