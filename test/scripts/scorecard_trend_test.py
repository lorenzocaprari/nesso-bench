import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "scorecard-trend"
CPU = "Test CPU"


def measure(datasets: dict[str, list[dict]], cpu: str = CPU) -> dict:
    return {"cpuModel": cpu, "datasets": [{"name": name, "engines": engines} for name, engines in datasets.items()]}


def nesso_measured(index: float, p50: float, grep_p50: float) -> list[dict]:
    return [
        {
            "engine": "nesso",
            "status": "ok",
            "indexWallSeconds": index,
            "modes": [{"mode": "auto", "queryLatencyMedianSeconds": p50}],
        },
        {"engine": "grep", "status": "ok", "queryLatencyMedianSeconds": grep_p50},
    ]


def timed(name: str, p50: float, index: float | None = None) -> list[dict]:
    entry: dict = {"engine": name, "status": "ok", "queryLatencyMedianSeconds": p50}
    if index is not None:
        entry["indexWallSeconds"] = index
    return [entry]


def quality(dataset: str, engines: list[dict]) -> dict:
    return {
        "schema_version": 4,
        "k": 10,
        "datasets": [{"dataset": dataset, "engines": engines, "query_count": 40}],
        "overall": {"engines": engines, "query_count": 40},
    }


def nesso_quality(mrr: float) -> dict:
    metrics = {"mrr": mrr, "ndcg_at_10": mrr, "recall_at_10": 1.0}
    mode = {
        "mode": "auto",
        "by_class": [{"class": "keyword", "metrics": metrics, "n": 40}],
        "overall": {"metrics": metrics, "n": 40},
    }
    return {"engine": "nesso", "status": "ok", "modes": [mode]}


def rival(name: str, mrr: float) -> dict:
    metrics = {"mrr": mrr, "ndcg_at_10": mrr, "recall_at_10": 1.0}
    return {
        "engine": name,
        "status": "ok",
        "by_class": [{"class": "keyword", "metrics": metrics, "n": 40}],
        "overall": {"metrics": metrics, "n": 40},
    }


def write_json(path: pathlib.Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def rows(text: str) -> dict[tuple[str, str], list[str]]:
    found = {}
    for line in text.splitlines():
        if not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells[0] in ("suite", "run") or set(cells[0]) <= {"-", ":", " "}:
            continue
        found[(cells[0], cells[1])] = cells
    return found


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False)


class ScorecardTrendTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = pathlib.Path(self.temp.name)
        self.main = self.base / "main"
        self.release = self.base / "release"
        self.history = self.base / "history"
        self._write_nesso_job()
        self._write_embeddings()
        self._write_history()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_nesso_job(self) -> None:
        main_measure = measure({
            "a": nesso_measured(10, 0.20, 0.02),
            "b": nesso_measured(30, 0.20, 0.06),
        })
        # The release run's grep is a different sample. Ratios must use the main run's grep.
        release_measure = measure({
            "a": nesso_measured(8, 0.10, 1.0),
            "b": nesso_measured(8, 0.10, 1.0),
        })
        write_json(self.main / "raw" / "2k" / "nesso.json", {**quality("hdfs", [nesso_quality(0.8)]), "measure": main_measure})
        write_json(
            self.release / "raw" / "2k" / "nesso.json",
            {**quality("hdfs", [nesso_quality(0.4)]), "measure": release_measure},
        )
        write_json(
            self.release / "raw" / "2k" / "bm25.json",
            {**quality("hdfs", [rival("bm25", 0.5)]), "measure": measure({"a": timed("bm25", 0.01, 2), "b": timed("bm25", 0.03, 6)})},
        )
        write_json(
            self.release / "raw" / "2k" / "opensearch.json",
            {"measure": measure({"a": timed("opensearch", 0.04, 20), "b": timed("opensearch", 0.12, 20)})},
        )
        write_json(
            self.release / "raw" / "2k" / "xerj.json",
            {"measure": measure({"a": timed("xerj", 0.002, 2), "b": timed("xerj", 0.006, 2)})},
        )
        write_json(
            self.release / "raw" / "2k" / "ripgrep.json",
            {"measure": measure({"a": timed("ripgrep", 0.02), "b": timed("ripgrep", 0.06)})},
        )

    def _write_embeddings(self) -> None:
        write_json(
            self.base / "diy" / "raw" / "2k" / "diy-faiss.json",
            {"measure": measure({"a": timed("diy-faiss", 0.013, 130.0)}, cpu="Embed CPU")},
        )
        write_json(
            self.base / "ck" / "raw" / "2k" / "ck.json",
            {"measure": measure({"a": timed("ck", 0.5, 50.5)}, cpu="Other CPU")},
        )

    def _history_report(self, run_id: str, created: str, event: str, index_s: float, p50: float, margin: float) -> None:
        payload = {
            "schema": 1,
            "runId": run_id,
            "createdAt": created,
            "event": event,
            "embeddings": {
                "diy-faiss": {
                    "cpuModel": "Old CPU",
                    "suites": {"2k": {"indexWallSeconds": index_s, "queryP50Seconds": p50, "cpuModel": "Old CPU"}},
                }
            },
            "margins": {
                "main": [{"suite": "2k", "system": "hdfs", "class": "keyword", "margin": margin, "bestOther": "bm25"}]
            },
        }
        write_json(self.history / run_id / "report.json", payload)

    def _write_history(self) -> None:
        self._history_report("100", "2026-11-09T16:23:00Z", "schedule", 100.0, 0.010, 0.05)
        self._history_report("200", "2026-11-16T16:23:00Z", "schedule", 110.0, 0.011, 0.10)
        # Later than the scheduled run, and a different margin: it must not be the comparison baseline.
        self._history_report("300", "2026-11-20T16:23:00Z", "workflow_dispatch", 120.0, 0.012, 0.90)

    def _args(self, *, record: pathlib.Path | None = None) -> list[str]:
        args = [
            "--main", str(self.main),
            "--release", str(self.release),
            "--embedding", str(self.base / "diy"),
            "--embedding", str(self.base / "ck"),
            "--history", str(self.history),
            "--run-id", "400",
            "--run-url", "https://github.com/lorenzocaprari/nesso-bench/actions/runs/400",
            "--event", "schedule",
            "--created-at", "2026-11-23T16:23:00Z",
            "--head-sha", "a" * 40,
            "--nesso-release", "0.3.1",
            "--nesso-main-version", "0.3.1+gabc",
        ]
        if record is not None:
            args += ["--record", str(record)]
        return args

    def test_in_job_ratios_and_margins_and_the_embedding_trend(self) -> None:
        done = run(*self._args())
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Development-only", done.stdout)
        self.assertIn("hosted runners", done.stdout)
        ratio_section, embedding_section = done.stdout.split("### Embedding engines", 1)
        self.assertNotIn("diy-faiss", ratio_section)
        self.assertNotIn("ck", ratio_section)
        table = rows(ratio_section)
        bm25 = table[("2k", "bm25")]
        self.assertEqual(bm25[2:10], ["8.000", "0.20×", "0.50×", "0.020", "0.10×", "0.20×", "0.50×", "0.50×"])
        opensearch = table[("2k", "opensearch")]
        self.assertEqual(opensearch[2:10], ["40.0", "1.00×", "2.50×", "0.080", "0.40×", "0.80×", "2.00×", "2.00×"])
        xerj = table[("2k", "xerj")]
        self.assertEqual(xerj[2:10], ["4.000", "0.10×", "0.25×", "0.004", "0.02×", "0.04×", "0.10×", "0.10×"])
        ripgrep = table[("2k", "ripgrep")]
        self.assertEqual(ripgrep[2], "—")
        self.assertEqual(ripgrep[6:10], ["0.20×", "0.40×", "1.00×", "—"])
        self.assertIn("CPU: Test CPU.", ratio_section)
        # main 0.8 - bm25 0.5 = +0.300; release 0.4 - 0.5 = -0.100; delta +0.400.
        # Previous scheduled run is 200 (margin +0.100), not the later dispatch (0.900).
        self.assertIn(
            "| 2k | hdfs | keyword | +0.300 | bm25 | -0.100 | bm25 | +0.400 | +0.100 | bm25 | +0.200 |",
            done.stdout,
        )
        self.assertNotIn("+0.900", done.stdout)
        self.assertIn("Previous scheduled run: 200", done.stdout)
        self.assertIn("#### diy-faiss", embedding_section)
        self.assertIn("`2k`, this engine only. Not a comparison with another engine.", embedding_section)
        self.assertIn("100.0", embedding_section)
        self.assertIn("130.0", embedding_section)
        self.assertIn("1.18×", embedding_section)
        self.assertIn("Not a comparison with another engine.", embedding_section)
        self.assertIn("`ck` `2k`: 1 of 4 runs kept. No timing shown.", embedding_section)
        self.assertNotIn("50.5", done.stdout)

    def test_ratios_are_withheld_when_the_job_does_not_share_a_cpu(self) -> None:
        write_json(
            self.release / "raw" / "2k" / "bm25.json",
            {"measure": measure({"a": timed("bm25", 0.01, 2)}, cpu="Other CPU")},
        )
        done = run(*self._args())
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("do not share one CPU", done.stdout)
        self.assertIn("No ratios are shown.", done.stdout)
        self.assertNotIn("0.20×", done.stdout)

    def test_record_keeps_samples_the_summary_does_not_show(self) -> None:
        record = self.base / "out"
        done = run(*self._args(record=record))
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads((record / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], 1)
        self.assertEqual(payload["event"], "schedule")
        self.assertTrue(payload["developmentOnly"])
        self.assertTrue(payload["hostedRunners"])
        self.assertEqual(payload["nessoRelease"], "0.3.1")
        self.assertEqual(payload["nessoMain"]["version"], "0.3.1+gabc")
        self.assertEqual(payload["embeddings"]["ck"]["suites"]["2k"]["indexWallSeconds"], 50.5)
        self.assertNotIn("marginFailures", payload)
        readme = (record / "README.md").read_text(encoding="utf-8")
        self.assertEqual(readme, done.stdout)
        self.assertNotIn("50.5", readme)

    def test_a_missing_directory_still_exits_zero(self) -> None:
        done = run(
            "--main", str(self.base / "missing"),
            "--release", str(self.base / "missing"),
            "--run-id", "1",
            "--event", "workflow_dispatch",
            "--created-at", "2026-11-23T00:00:00Z",
            "--nesso-release", "0.3.1",
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("No nesso quality report", done.stdout)
        self.assertIn("No measured in-job engine reports.", done.stdout)
        self.assertIn("Previous scheduled run: none is committed yet.", done.stdout)

    def test_rejects_a_bad_release_version(self) -> None:
        done = run(
            "--main", str(self.main),
            "--release", str(self.release),
            "--run-id", "1",
            "--event", "schedule",
            "--created-at", "2026-11-23T00:00:00Z",
            "--nesso-release", "main",
        )
        self.assertNotEqual(done.returncode, 0)


if __name__ == "__main__":
    unittest.main()
