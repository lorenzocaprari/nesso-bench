import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "scorecard-ratios"
CPU = "Test CPU"


def nesso_entry(index: float, p50_auto: float, p50_dense: float = 9.0, status: str = "ok") -> dict:
    return {
        "engine": "nesso",
        "status": status,
        "indexWallSeconds": index,
        "modes": [
            {"mode": "auto", "queryLatencyMedianSeconds": p50_auto},
            {"mode": "dense", "queryLatencyMedianSeconds": p50_dense},
        ],
    }


def engine(name: str, p50: float, index: float | None = None, status: str = "ok") -> dict:
    return {"engine": name, "status": status, "indexWallSeconds": index, "queryLatencyMedianSeconds": p50}


def report(datasets: dict[str, list[dict]], cpu: str = CPU) -> dict:
    return {
        "schema_version": 4,
        "measure": {"cpuModel": cpu, "datasets": [{"name": name, "engines": engines} for name, engines in datasets.items()]},
    }


def write(directory: pathlib.Path, suite: str, group: str, payload: dict) -> None:
    target = directory / "raw" / suite / f"{group}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload), encoding="utf-8")


def machine(directory: pathlib.Path, version: str, source: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "machine.json").write_text(json.dumps({"nessoVersion": version, "nessoSource": source}), encoding="utf-8")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False)


def rows(text: str) -> dict[tuple[str, str], list[str]]:
    found = {}
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if line.startswith("| ") and cells[0] not in ("suite",) and not cells[0].startswith("---"):
            found[(cells[0], cells[1].split(" ")[0])] = cells
    return found


class ScorecardRatiosTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = pathlib.Path(self.temp.name)
        self.main = self.base / "main"
        self.baseline = self.base / "baseline"
        machine(self.main, "0.3.1+gabc", "binary")
        machine(self.baseline, "0.3.1", "release")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def keywords(self, suite: str, datasets: dict[str, tuple[float, float, float]]) -> None:
        """datasets: name -> (bm25 index s, bm25 p50, ripgrep p50)."""
        write(self.baseline, suite, "bm25", report({name: [engine("bm25", p50, index)] for name, (index, p50, _) in datasets.items()}))
        write(self.baseline, suite, "ripgrep", report({name: [engine("ripgrep", rg)] for name, (_, _, rg) in datasets.items()}))

    def test_index_ratio_sums_and_query_ratio_is_median_of_dataset_ratios(self) -> None:
        self.keywords("2k", {"a": (1.0, 0.001, 0.01), "b": (3.0, 0.001, 0.02), "c": (4.0, 0.001, 0.05)})
        write(self.main, "2k", "nesso", report({
            "a": [nesso_entry(10.0, 0.2), engine("grep", 0.002)],
            "b": [nesso_entry(20.0, 0.4), engine("grep", 0.004)],
            "c": [nesso_entry(10.0, 0.5), engine("grep", 0.001)],
        }))
        write(self.baseline, "2k", "nesso", report({
            "a": [nesso_entry(4.0, 0.1), engine("grep", 0.002)],
            "b": [nesso_entry(4.0, 0.1), engine("grep", 0.002)],
            "c": [nesso_entry(8.0, 0.1), engine("grep", 0.002)],
        }))
        done = run("--keywords", str(self.baseline), f"main={self.main}", f"baseline={self.baseline}")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("development-only", done.stdout)
        table = rows(done.stdout)
        main = table[("2k", "main")]
        # index: (10 + 20 + 10) / (1 + 3 + 4) = 5.
        self.assertEqual(main[1], "main (0.3.1+gabc (binary))")
        self.assertEqual(main[2:5], ["40.0", "8.000", "5.00×"])
        # p50 ÷ grep: median of 100, 100, 500 = 100; ÷ ripgrep: median of 20, 20, 10 = 20.
        self.assertEqual(main[5:8], ["0.400", "100.0×", "20.0×"])
        baseline = table[("2k", "baseline")]
        self.assertEqual(baseline[1], "baseline (0.3.1)")
        # index: 16 / 8 = 2; grep: 50 each; ripgrep: 10, 5, 2 -> 5.
        self.assertEqual(baseline[4], "2.00×")
        self.assertEqual(baseline[6:8], ["50.0×", "5.00×"])
        self.assertNotIn("Warning", done.stdout)
        self.assertIn("CPU: Test CPU (baseline, bm25, main, ripgrep).", done.stdout)

    def test_mode_selects_the_nesso_p50(self) -> None:
        self.keywords("json", {"a": (1.0, 0.001, 0.1)})
        write(self.main, "json", "nesso", report({"a": [nesso_entry(1.0, 0.2, p50_dense=0.3), engine("grep", 0.1)]}))
        done = run("--keywords", str(self.baseline), "--mode", "dense", f"main={self.main}")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(rows(done.stdout)[("json", "main")][6:8], ["3.00×", "3.00×"])
        self.assertIn("nesso mode `dense`", done.stdout)

    def test_only_datasets_both_finished_count(self) -> None:
        write(self.baseline, "2k", "bm25", report({"a": [engine("bm25", 0.001, 2.0)], "b": [engine("bm25", 0.001, 100.0, status="failed")]}))
        write(self.main, "2k", "nesso", report({
            "a": [nesso_entry(4.0, 0.2), engine("grep", 0.1)],
            "b": [nesso_entry(50.0, 0.2), engine("grep", 0.1)],
        }))
        done = run("--keywords", str(self.baseline), f"main={self.main}")
        main = rows(done.stdout)[("2k", "main")]
        self.assertEqual(main[2:5], ["4.000", "2.000", "2.00×"])
        # No ripgrep report at all: a dash, not an error.
        self.assertEqual(main[7], "—")
        self.assertEqual(main[6], "2.00×")

    def test_suites_follow_the_scorecard_order_and_skip_quality_only_reports(self) -> None:
        for suite in ("bgl-needle-100k", "json", "2k"):
            write(self.main, suite, "nesso", report({"a": [nesso_entry(1.0, 0.2), engine("grep", 0.1)]}))
        # The bundle suite is quality only: no measure section, so no row.
        write(self.main, "bundle", "nesso", {"schema_version": 4, "datasets": []})
        done = run("--keywords", str(self.baseline), f"main={self.main}")
        suites = [key[0] for key in rows(done.stdout)]
        self.assertEqual(suites, ["2k", "json", "bgl-needle-100k"])

    def test_warns_when_reports_come_from_different_cpus(self) -> None:
        write(self.baseline, "2k", "bm25", report({"a": [engine("bm25", 0.001, 1.0)]}, cpu="Other CPU"))
        write(self.main, "2k", "nesso", report({"a": [nesso_entry(1.0, 0.2), engine("grep", 0.1)]}))
        done = run("--keywords", str(self.baseline), f"main={self.main}")
        self.assertIn("**Warning:**", done.stdout)
        self.assertIn("Other CPU (bm25)", done.stdout)

    def test_no_reports_still_exits_zero(self) -> None:
        done = run("--keywords", str(self.base / "missing"), f"main={self.base / 'missing'}")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("No measured nesso reports found.", done.stdout)

    def test_rejects_a_build_without_a_name(self) -> None:
        done = run("--keywords", str(self.baseline), str(self.main))
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("NAME=DIR", done.stderr)


if __name__ == "__main__":
    unittest.main()
