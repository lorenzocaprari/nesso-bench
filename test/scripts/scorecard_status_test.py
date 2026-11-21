import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "scorecard-status"


def results(directory: pathlib.Path, runs: list[dict], machine: dict | None = None) -> pathlib.Path:
    directory.mkdir(parents=True)
    (directory / "status.json").write_text(json.dumps({"runs": runs}), encoding="utf-8")
    if machine is not None:
        (directory / "machine.json").write_text(json.dumps(machine), encoding="utf-8")
    return directory


def run_status(*directories: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, directories)], capture_output=True, text=True, check=False)


MACHINE = {"cpuModel": "Test CPU", "nproc": 4, "memTotalBytes": 16 * 2**30, "memoryMax": "12G", "developmentOnly": True}


class ScorecardStatusTest(unittest.TestCase):
    def test_table_of_group_by_suite_with_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            one = results(
                base / "scorecard-smoke-nesso",
                [
                    {"suite": "2k", "group": "nesso", "outcome": "ok", "exitCode": 0, "wallSeconds": 42.0},
                    {"suite": "bgl-needle-100k", "group": "nesso", "outcome": "ok", "exitCode": 0, "wallSeconds": 600.0},
                ],
                MACHINE,
            )
            two = results(
                base / "scorecard-smoke-vecgrep",
                [
                    {"suite": "2k", "group": "vecgrep", "outcome": "ok", "exitCode": 0, "wallSeconds": 9000.0},
                    {"suite": "bgl-needle-100k", "group": "vecgrep", "outcome": "out-of-memory (3G)", "exitCode": 137, "wallSeconds": 30.0},
                ],
                MACHINE,
            )
            done = run_status(one, two)
        self.assertEqual(done.returncode, 0, done.stderr)
        out = done.stdout
        self.assertIn("| engine group | 2k | bgl-needle-100k |", out)
        self.assertIn("| nesso | ok (42 s) | ok (10 min) |", out)
        self.assertIn("| vecgrep | ok (2.5 h) | out-of-memory (3G) (30 s) |", out)
        self.assertIn("3 of 4 runs ok.", out)
        # What did not finish is listed with its exit code.
        self.assertIn("| bgl-needle-100k | vecgrep | out-of-memory (3G) | 137 |", out)
        self.assertIn("| scorecard-smoke-nesso | Test CPU | 4 | 16 GiB | 12G | yes |", out)

    def test_a_missing_cell_is_a_dash_and_unreadable_directories_are_named(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            good = results(base / "a", [{"suite": "2k", "group": "g1", "outcome": "ok", "exitCode": 0, "wallSeconds": 1.0},
                                        {"suite": "json", "group": "g2", "outcome": "timeout", "exitCode": 124, "wallSeconds": 28800.0}])
            (base / "empty").mkdir()
            done = run_status(good, base / "empty")
        self.assertEqual(done.returncode, 0)
        self.assertIn("| g1 | ok (1 s) | — |", done.stdout)
        self.assertIn("| g2 | — | timeout (8.0 h) |", done.stdout)
        self.assertIn("No readable status.json in: empty.", done.stdout)

    def test_no_readable_directory_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            done = run_status(pathlib.Path(temp))
        self.assertEqual(done.returncode, 1)
        self.assertIn("No runs found.", done.stdout)

    def test_reads_a_real_status_file_layout(self) -> None:
        # The layout scripts/scorecard writes: runs[] with these keys, plus merges.
        with tempfile.TemporaryDirectory() as temp:
            directory = pathlib.Path(temp) / "0.3.1"
            directory.mkdir()
            (directory / "status.json").write_text(
                json.dumps(
                    {
                        "finishedAt": "2026-11-21T00:00:00Z",
                        "merges": [{"suite": "2k", "merged": "merged/2k.json", "inputs": 1}],
                        "runs": [{"suite": "2k", "group": "nesso", "engines": ["nesso", "grep"], "threads": None, "outcome": "ok",
                                  "exitCode": 0, "wallSeconds": 10.5, "report": "raw/2k/nesso.json", "fp32": False, "merged": True}],
                    }
                ),
                encoding="utf-8",
            )
            done = run_status(directory)
        self.assertEqual(done.returncode, 0)
        self.assertIn("| nesso | ok (10 s) |", done.stdout)


if __name__ == "__main__":
    unittest.main()
