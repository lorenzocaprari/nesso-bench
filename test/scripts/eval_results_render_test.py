import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
RENDER = ROOT / "scripts" / "eval-results-render"


def metrics(value: float) -> dict[str, float]:
    return {"mrr": value, "ndcg_at_10": value, "recall_at_10": value}


def entry(scores: list[float], prefix: str) -> dict:
    queries = [{"class": "cause", "id": f"{prefix}{i}", "metrics": metrics(score)} for i, score in enumerate(scores)]
    mean = sum(scores) / len(scores)
    bucket = {"class": "cause", "metrics": metrics(mean), "n": len(scores)}
    return {"by_class": [bucket], "overall": {"metrics": metrics(mean), "n": len(scores)}, "queries": queries}


def nesso(scores: list[float], prefix: str) -> dict:
    return {"engine": "nesso", "modes": [{"mode": "auto", **entry(scores, prefix)}], "status": "ok"}


def other(name: str, scores: list[float], prefix: str) -> dict:
    return {"engine": name, "status": "ok", **entry(scores, prefix)}


def measured(name: str, wall: float, spread: list[float]) -> dict:
    return {
        "engine": name,
        "indexBytes": 20 * 2**20,
        "indexPeakRssBytes": 300 * 2**20,
        "indexToLogRatio": 2.0,
        "indexWallSeconds": wall,
        "queryLatencyMedianSeconds": 0.01,
        "queryLatencyP95Seconds": 0.02,
        "queryPeakRssBytes": 100 * 2**20,
        "queryWallSeconds": 0.5,
        "range": {"indexWallSeconds": spread},
        "status": "ok",
        "timeToFirstResultSeconds": 1.5,
    }


def results_dir(directory: pathlib.Path) -> pathlib.Path:
    results = directory / "0.3.1"
    (results / "merged").mkdir(parents=True)
    (results / "raw" / "2k").mkdir(parents=True)
    # bm25 wins every query on hdfs-2k and loses every one on bgl-2k: a tie pooled, a loss on hdfs-2k.
    datasets = [
        {"dataset": "hdfs-2k", "engines": [nesso([0.0] * 10, "h"), other("bm25", [1.0] * 10, "h")], "query_count": 10},
        {"dataset": "bgl-2k", "engines": [nesso([1.0] * 10, "b"), other("bm25", [0.0] * 10, "b")], "query_count": 10},
    ]
    report = {
        "datasets": datasets,
        "k": 10,
        "measure": {
            "datasets": [
                {
                    "engines": [measured("bm25", 0.5, [0.4, 0.6]), {"engine": "ck", "reason": "missing", "status": "skipped"}],
                    "logBytes": 2 * 2**20,
                    "logLines": 1000,
                    "name": "hdfs-2k",
                }
            ],
            "tool": {"bm25": "sqlite 3", "nesso": "0.3.1"},
        },
        "overall": {"engines": [nesso([0.0] * 10 + [1.0] * 10, "x"), other("bm25", [1.0] * 10 + [0.0] * 10, "x")], "query_count": 20},
        "schema_version": 4,
    }
    # The overall row pools the datasets' queries, which carry the dataset in their key.
    report["overall"]["engines"] = [
        {"engine": "nesso", "modes": [{"mode": "auto", **entry([0.5] * 2, "o")}], "status": "ok"},
        other("bm25", [0.5] * 2, "o"),
    ]
    (results / "merged" / "2k.json").write_text(json.dumps(report), encoding="utf-8")
    threads = {"measure": {"datasets": [{"engines": [measured("nesso", 2.0, [2.0, 2.0])], "logBytes": 2**20, "logLines": 1000, "name": "hdfs-2k"}]}}
    (results / "raw" / "2k" / "nesso-threads-1.json").write_text(json.dumps(threads), encoding="utf-8")
    machine = {
        "cpuModel": "Test CPU",
        "developmentOnly": False,
        "memTotalBytes": 64 * 2**30,
        "memoryMax": "48G",
        "nessoVersion": "0.3.1",
        "nproc": 16,
        "timeoutHours": 8,
        "tools": {"python": "3.12"},
    }
    (results / "machine.json").write_text(json.dumps(machine), encoding="utf-8")
    status = {
        "merges": [{"inputs": 2, "merged": "merged/2k.json", "suite": "2k"}],
        "runs": [
            {"group": "nesso", "outcome": "ok", "suite": "2k", "wallSeconds": 10},
            {"group": "vecgrep", "outcome": "out-of-memory (48G)", "suite": "bgl-needle-1m", "wallSeconds": 7200},
        ],
    }
    (results / "status.json").write_text(json.dumps(status), encoding="utf-8")
    return results


class EvalResultsRenderTest(unittest.TestCase):
    def render(self, results: pathlib.Path, out: pathlib.Path) -> str:
        completed = subprocess.run([sys.executable, str(RENDER), str(results), "--out", str(out)], capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return out.read_text(encoding="utf-8")

    def test_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = pathlib.Path(temp)
            results = results_dir(directory)
            page = self.render(results, directory / "page.md")
            again = self.render(results, directory / "again.md")
        self.assertEqual(page, again)
        self.assertTrue(page.startswith("# nesso 0.3.1 scorecard\n"))
        self.assertNotIn("Development only", page)
        self.assertIn("| CPU | Test CPU (16 logical CPUs, SMT None) |", page)
        # A loss on one system is listed even when the pooled row ties.
        self.assertIn("| 2k | hdfs-2k | cause | bm25 | 1.000 | -1.000 | [-1.000, -1.000] |", page)
        self.assertNotIn("| 2k | bgl-2k |", page.split("## Quality")[0])
        self.assertIn("| nesso/auto | cause | 2 | 0.500 | 0.500 | 0.500 | headline | — |", page)
        # The pooled interval pairs all 20 per-dataset queries: ten wins and ten losses tie.
        self.assertIn("| bm25 | cause | 2 | 0.500 | 0.500 | 0.500 | +0.000 [-0.400, +0.400] | tie |", page)
        # Speed: lines/s from the median, the range when repeats differ, skipped engines kept.
        self.assertIn("### 2k: hdfs-2k (1,000 lines, 2.0 MiB)", page)
        self.assertIn("| bm25 | 2,000 | 0.50 (0.40–0.60) | 300 | 20 (2.00×) | 10.0 | 20.0 | 100 | 1.50 |", page)
        self.assertIn("| ck | skipped: missing |", page)
        self.assertIn("### 2k at NESSO_THREADS=1: hdfs-2k", page)
        self.assertIn("| nesso | 500 | 2.00 | 300 |", page)
        self.assertIn("| bgl-needle-1m | vecgrep | out-of-memory (48G) | 2.00 h |", page)
        self.assertIn("| bm25 | sqlite 3 |", page)

    def test_development_banner_and_no_losses(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = pathlib.Path(temp)
            results = results_dir(directory)
            machine = json.loads((results / "machine.json").read_text(encoding="utf-8"))
            (results / "machine.json").write_text(json.dumps({**machine, "developmentOnly": True}), encoding="utf-8")
            report = json.loads((results / "merged" / "2k.json").read_text(encoding="utf-8"))
            report["datasets"] = report["datasets"][1:]
            (results / "merged" / "2k.json").write_text(json.dumps(report), encoding="utf-8")
            status = {"merges": [{"merged": "merged/2k.json", "suite": "2k"}], "runs": []}
            (results / "status.json").write_text(json.dumps(status), encoding="utf-8")
            page = self.render(results, directory / "page.md")
        self.assertIn("> **Development only.**", page)
        self.assertIn("No ranker beats nesso's headline mode", page)
        self.assertIn("Every run finished.", page)
        # Without recorded reasons (older machine.json), the generic one is kept.
        self.assertIn("This run allowed WSL, a busy machine, or local changes; do not publish", page)
        self.assertIn("(the released binary and its shipped int8 model)", page)

    def test_binary_built_outside_a_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = pathlib.Path(temp)
            results = results_dir(directory)
            machine = json.loads((results / "machine.json").read_text(encoding="utf-8"))
            reason = "nesso is a binary built outside a pinned release (0.3.1+gb20ff665cbb6)"
            machine.update({
                "developmentOnly": True,
                "developmentReasons": [reason],
                "nessoBinarySha256": "ab" * 32,
                "nessoModel": {"dir": "models", "model_onnx_sha256": "cd" * 32, "model_onnx_bytes": 4},
                "nessoSource": "binary",
                "nessoVersion": "0.3.1+gb20ff665cbb6",
                "nessoVersionOutput": "0.3.1+gb20ff665cbb6",
            })
            (results / "machine.json").write_text(json.dumps(machine), encoding="utf-8")
            page = self.render(results, directory / "page.md")
        self.assertTrue(page.startswith("# nesso 0.3.1+gb20ff665cbb6 scorecard\n"))
        self.assertIn(f"> **Development only:** {reason}. Do not publish its numbers.", page)
        self.assertIn("(a binary built outside a release, with the model directory it was given)", page)
        self.assertIn("| nesso | 0.3.1+gb20ff665cbb6 (binary built outside a release) |", page)
        self.assertIn(f"| nesso binary sha256 | {'ab' * 32} |", page)
        self.assertIn(f"| Model (model.onnx sha256) | {'cd' * 32} (models) |", page)

    def test_unstable_ranker_is_marked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = pathlib.Path(temp)
            results = results_dir(directory)
            report = json.loads((results / "merged" / "2k.json").read_text(encoding="utf-8"))
            repeat = {"changed_queries": ["h1"], "identical": False, "runs": 3}
            report["datasets"][0]["engines"][1]["quality_repeat"] = repeat
            report["overall"]["engines"][1]["quality_repeat"] = repeat
            (results / "merged" / "2k.json").write_text(json.dumps(report), encoding="utf-8")
            page = self.render(results, directory / "page.md")
        self.assertIn("| 2k | hdfs-2k | cause | bm25 † | 1.000 | -1.000 | [-1.000, -1.000] |", page)
        self.assertIn("| bm25 † | cause | 2 |", page)
        self.assertEqual(page.count("† The ranker's rankings changed between repeated quality runs"), 2)

    def test_int8_against_fp32(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = pathlib.Path(temp)
            results = results_dir(directory)
            # A nesso-only report, as the nesso-fp32 run writes it: fp32 finds what int8 missed on hdfs-2k.
            datasets = [
                {"dataset": "hdfs-2k", "modes": [{"mode": "auto", **entry([1.0] * 10, "h")}], "query_count": 10},
                {"dataset": "bgl-2k", "modes": [{"mode": "auto", **entry([1.0] * 10, "b")}], "query_count": 10},
            ]
            measure = {
                "datasets": [{"engines": [measured("nesso", 3.0, [3.0, 3.0])], "logBytes": 2**20, "logLines": 1000, "name": "hdfs-2k"}],
                "tool": {"nesso-model": "fp32 onnx 759c3cd2b7fe 90387606B"},
            }
            fp32 = {
                "datasets": datasets,
                "k": 10,
                "measure": measure,
                "overall": {"modes": [{"mode": "auto", **entry([1.0] * 20, "x")}], "query_count": 20},
                "schema_version": 3,
            }
            (results / "raw" / "2k" / "nesso-fp32.json").write_text(json.dumps(fp32), encoding="utf-8")
            page = self.render(results, directory / "page.md")
        section = page.split("## int8 against fp32")[1].split("## Speed and memory")[0]
        # Pooled over both systems: int8 loses all ten hdfs-2k queries and ties bgl-2k.
        self.assertIn("| nesso/auto | cause | 20 | 0.500 | 1.000 | -0.500 [", section)
        self.assertIn("| loss |", section)
        self.assertIn("### 2k with the fp32 model: hdfs-2k", page)
        self.assertIn("| nesso | 333 | 3.00 | 300 |", page)
        self.assertIn("| nesso-model (fp32) | fp32 onnx 759c3cd2b7fe 90387606B |", page)

    def test_no_fp32_section_without_its_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = pathlib.Path(temp)
            page = self.render(results_dir(directory), directory / "page.md")
        self.assertNotIn("int8 against fp32", page)
        self.assertNotIn("fp32 model", page)

    def test_missing_results_fail_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            completed = subprocess.run(
                [sys.executable, str(RENDER), temp, "--out", str(pathlib.Path(temp) / "x.md")], capture_output=True, text=True, check=False
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("cannot read", completed.stderr)


if __name__ == "__main__":
    unittest.main()
