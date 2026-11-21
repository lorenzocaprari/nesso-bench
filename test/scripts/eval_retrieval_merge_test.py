import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MERGE = ROOT / "scripts" / "eval-retrieval-merge"


def metrics(value: float) -> dict[str, float]:
    return {"mrr": value, "ndcg_at_10": value, "precision_at_10": value, "recall_at_10": value}


def engine(name: str, value: float) -> dict:
    bucket = {"found_at_depth": 1.0, "median_first_hit_rank": 1, "metrics": metrics(value), "n": 2}
    return {
        "by_class": [{"class": "symptom", **bucket}, {"class": "keyword", "n": 0}],
        "engine": name,
        "overall": bucket,
        "status": "ok",
    }


def needle_report(*engines: dict, dataset: str = "bgl-needle-100k", lines: int = 100) -> dict:
    return {
        "datasets": [{"dataset": dataset, "engines": list(engines), "lines": lines, "query_count": 2}],
        "depth": 100,
        "k": 10,
        "kind": "needle",
        "overall": {"engines": list(engines), "query_count": 2},
        "schema_version": 1,
    }


def retrieval_report(*engines: dict) -> dict:
    return {
        "datasets": [{"dataset": "hdfs-2k", "engines": list(engines), "query_count": 2}],
        "k": 10,
        "overall": {"engines": list(engines), "query_count": 2},
        "schema_version": 4,
    }


def measured(report: dict, *rows: str, tool: dict | None = None, log_lines: int = 100, **machine: object) -> dict:
    """Attach a measure section with one row per engine name."""
    section = {
        "cpuModel": "Test CPU",
        "datasets": [
            {
                "engines": [{"engine": name, "indexWallSeconds": 1.0, "range": {}, "status": "ok"} for name in rows],
                "logBytes": 1000,
                "logLines": log_lines,
                "name": report["datasets"][0]["dataset"],
            }
        ],
        "memTotalBytes": 64 * 2**30,
        "nproc": 8,
        "platform": "Linux-test",
        "repeat": 3,
        "threads": None,
        "tool": tool if tool is not None else {name: f"{name} 1.0" for name in rows},
    }
    section.update(machine)
    return {**report, "measure": section}


class EvalRetrievalMergeTest(unittest.TestCase):
    def run_merge(self, *reports: dict, markdown: bool = False) -> tuple[subprocess.CompletedProcess[str], dict | None, str]:
        with tempfile.TemporaryDirectory() as temp:
            directory = pathlib.Path(temp)
            paths = []
            for index, payload in enumerate(reports):
                path = directory / f"r{index}.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                paths.append(str(path))
            out = directory / "merged.json"
            md = directory / "merged.md"
            command = [sys.executable, str(MERGE), *paths, "--out", str(out)]
            if markdown:
                command += ["--markdown", str(md)]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            merged = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
            text = md.read_text(encoding="utf-8") if md.exists() else ""
        return result, merged, text

    def test_merges_engines_in_input_order(self) -> None:
        result, merged, text = self.run_merge(
            needle_report(engine("diy-faiss", 0.4)),
            needle_report(engine("ck", 0.1), {"engine": "vecgrep", "reason": "missing", "status": "skipped"}),
            markdown=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        assert merged is not None
        self.assertEqual([row["engine"] for row in merged["overall"]["engines"]], ["diy-faiss", "ck", "vecgrep"])
        self.assertEqual([row["engine"] for row in merged["datasets"][0]["engines"]], ["diy-faiss", "ck", "vecgrep"])
        self.assertEqual(merged["kind"], "needle")
        self.assertIn("| diy-faiss | symptom | 2 | 0.400 | 0.400 | 0.400 | 1.000 |", text)
        self.assertIn("| vecgrep | skipped: missing |", text)
        # Empty classes add no row.
        self.assertNotIn("| keyword |", text)

    def test_retrieval_markdown_uses_recall(self) -> None:
        result, _merged, text = self.run_merge(retrieval_report(engine("bm25", 1.0)), markdown=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("| engine | class | n | MRR | nDCG@10 | recall@10 |", text)

    def test_rejects_mismatches(self) -> None:
        cases = [
            ((needle_report(engine("a", 1.0)), needle_report(engine("a", 0.5))), "is in both"),
            ((needle_report(engine("a", 1.0)), retrieval_report(engine("b", 1.0))), "report;"),
            ((needle_report(engine("a", 1.0)), needle_report(engine("b", 1.0), dataset="other")), "has datasets"),
            ((needle_report(engine("a", 1.0)), needle_report(engine("b", 1.0), lines=5)), "differs outside engines"),
            (({"datasets": [], "schema_version": 3, "overall": {"engines": []}},), "schema_version 4"),
        ]
        for reports, message in cases:
            result, _merged, _text = self.run_merge(*reports)
            self.assertNotEqual(result.returncode, 0, message)
            self.assertIn(message, result.stderr)

    def test_merges_measure_sections(self) -> None:
        result, merged, _text = self.run_merge(
            measured(needle_report(engine("nesso", 0.6)), "nesso"),
            measured(needle_report(engine("diy-faiss", 0.4)), "diy-faiss"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        assert merged is not None
        measure = merged["measure"]
        self.assertEqual([row["engine"] for row in measure["datasets"][0]["engines"]], ["nesso", "diy-faiss"])
        self.assertEqual(measure["tool"], {"diy-faiss": "diy-faiss 1.0", "nesso": "nesso 1.0"})
        self.assertEqual(measure["cpuModel"], "Test CPU")

    def test_rejects_measure_mismatches(self) -> None:
        nesso = needle_report(engine("nesso", 0.6))
        diy = needle_report(engine("diy-faiss", 0.4))
        cases = [
            ((measured(nesso, "nesso"), diy), "has a measure section and"),
            ((nesso, measured(diy, "diy-faiss")), "has a measure section and"),
            ((measured(nesso, "nesso"), measured(diy, "diy-faiss", cpuModel="Other CPU")), "measure cpuModel"),
            ((measured(nesso, "nesso"), measured(diy, "diy-faiss", memTotalBytes=16 * 2**30)), "measure memTotalBytes"),
            ((measured(nesso, "nesso"), measured(diy, "diy-faiss", nproc=4)), "measure nproc"),
            ((measured(nesso, "nesso"), measured(diy, "diy-faiss", repeat=1)), "measure repeat"),
            ((measured(nesso, "nesso"), measured(diy, "diy-faiss", threads="1")), "measure threads"),
            (
                (measured(nesso, "nesso", tool={"nesso-model": "a"}), measured(diy, "diy-faiss", tool={"nesso-model": "b"})),
                "measure tool nesso-model",
            ),
            ((measured(nesso, "nesso"), measured(diy, "nesso")), "measured engine nesso is in both"),
            ((measured(nesso, "nesso"), measured(diy, "diy-faiss", log_lines=5)), "logLines differs"),
        ]
        for reports, message in cases:
            result, _merged, _text = self.run_merge(*reports)
            self.assertNotEqual(result.returncode, 0, message)
            self.assertIn(message, result.stderr)


if __name__ == "__main__":
    unittest.main()
