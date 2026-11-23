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
        self.assertIn("| results | nesso | CPU | logical CPUs | RAM | memory cap | development only |", out)
        self.assertIn("| scorecard-smoke-nesso | ? | Test CPU | 4 | 16 GiB | 12G | yes |", out)

    def test_machine_row_names_the_nesso_and_a_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            run = [{"suite": "2k", "group": "nesso", "outcome": "ok", "exitCode": 0, "wallSeconds": 1.0}]
            release = results(base / "release", run, {**MACHINE, "nessoVersion": "0.3.1", "nessoSource": "release", "developmentOnly": False})
            built = results(base / "built", run, {**MACHINE, "nessoVersion": "0.3.1+gb20ff665cbb6", "nessoSource": "binary"})
            done = run_status(release, built)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("| release | 0.3.1 | Test CPU | 4 | 16 GiB | 12G | no |", done.stdout)
        self.assertIn("| built | 0.3.1+gb20ff665cbb6 (binary) | Test CPU | 4 | 16 GiB | 12G | yes |", done.stdout)

    def test_a_group_in_two_directories_gets_a_row_per_directory(self) -> None:
        # The smoke workflow's nesso job scores main and the release baseline;
        # both are group nesso, and the baseline directory also has the keyword engines.
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            main = results(base / "scorecard-smoke-nesso-main", [
                {"suite": "2k", "group": "nesso", "outcome": "ok", "exitCode": 0, "wallSeconds": 5.0},
            ])
            baseline = results(base / "scorecard-smoke-nesso-baseline", [
                {"suite": "2k", "group": "nesso", "outcome": "failed (exit 1)", "exitCode": 1, "wallSeconds": 7.0},
                {"suite": "2k", "group": "bm25", "outcome": "ok", "exitCode": 0, "wallSeconds": 3.0},
            ])
            done = run_status(main, baseline)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("| nesso (scorecard-smoke-nesso-main) | ok (5 s) |", done.stdout)
        self.assertIn("| nesso (scorecard-smoke-nesso-baseline) | failed (exit 1) (7 s) |", done.stdout)
        self.assertIn("| bm25 | ok (3 s) |", done.stdout)
        self.assertIn("| 2k | nesso (scorecard-smoke-nesso-baseline) | failed (exit 1) | 1 |", done.stdout)
        self.assertIn("2 of 3 runs ok.", done.stdout)

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

    def test_no_times_leaves_wall_times_out_of_the_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            one = results(
                base / "nesso",
                [{"suite": "2k", "group": "nesso", "outcome": "ok", "exitCode": 0, "wallSeconds": 42.0}],
                MACHINE,
            )
            done = subprocess.run([sys.executable, str(SCRIPT), "--no-times", str(one)], capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("| nesso | ok |", done.stdout)
        self.assertNotIn("42 s", done.stdout)
        self.assertNotIn("ok (", done.stdout)

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
