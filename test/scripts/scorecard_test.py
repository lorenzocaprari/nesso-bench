import hashlib
import importlib.machinery
import importlib.util
import json
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "scorecard"


def load_scorecard():
    loader = importlib.machinery.SourceFileLoader("scorecard", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    # Dataclasses look their module up while the class is built.
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


class ScorecardPlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_scorecard()

    def test_plan_covers_every_suite_and_group(self) -> None:
        mod = self.mod
        runs = mod.plan(list(mod.SUITES), list(mod.GROUPS), threads_1=False)
        self.assertEqual(len(runs), len(mod.SUITES) * len(mod.GROUPS))
        self.assertTrue(all(run.merged for run in runs))
        with_threads = mod.plan(list(mod.SUITES), list(mod.GROUPS), threads_1=True)
        extra = with_threads[len(runs):]
        self.assertEqual([run.group.name for run in extra], ["nesso-threads-1"] * sum(suite.measure for suite in mod.SUITES))
        # NESSO_THREADS is part of a measured report's setting, so these stay out of the merge.
        self.assertTrue(all(not run.merged for run in extra))
        # No nesso group selected: no threads-1 runs either.
        only_bm25 = mod.plan(list(mod.SUITES), [mod.GROUPS[2]], threads_1=True, fp32=True)
        self.assertEqual({run.group.name for run in only_bm25}, {"bm25"})

    def test_fp32_runs_are_separate_and_use_the_fp32_model(self) -> None:
        mod = self.mod
        runs = mod.plan(list(mod.SUITES), list(mod.GROUPS), threads_1=True, fp32=True)
        fp32 = [run for run in runs if run.group.fp32]
        self.assertEqual([run.suite.name for run in fp32], [suite.name for suite in mod.SUITES])
        # A different model is a different setting: kept out of the suite merge.
        self.assertTrue(all(not run.merged for run in fp32))
        out = pathlib.Path("/results/0.3.1")
        argv = fp32[0].command(out, "py", {"NESSO_FP32_MODEL_DIR": "/fp32"})
        self.assertEqual(argv[argv.index("--model-dir") + 1], "/fp32")
        self.assertEqual(argv[argv.index("--modes") + 1], mod.NESSO_MODES)
        self.assertEqual(argv[argv.index("--out") + 1], "/results/0.3.1/raw/2k/nesso-fp32.json")
        self.assertEqual([argv[i + 1] for i, arg in enumerate(argv) if arg == "--engine"], ["nesso"])
        self.assertNotIn("--model-dir", mod.Run(mod.SUITES[0], mod.GROUPS[0]).command(out, "py", {"NESSO_FP32_MODEL_DIR": "/fp32"}))

    def test_repeat_override_applies_to_measured_suites_only(self) -> None:
        def dry_run(*extra: str) -> list[dict]:
            done = subprocess.run(
                [sys.executable, str(SCRIPT), "--nesso-version", "0.3.1", "--dry-run", "--groups", "nesso,xerj-neural", *extra],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            return [json.loads(line) for line in done.stdout.splitlines()]

        def value(run: dict, flag: str) -> str | None:
            argv = run["argv"]
            return argv[argv.index(flag) + 1] if flag in argv else None

        for run in dry_run("--suites", "2k,bundle", "--repeat", "1"):
            if run["suite"] == "2k":
                self.assertEqual(value(run, "--repeat"), "1")
                # xerj's quality repeats follow the suite, so a repeat of 1 adds none.
                self.assertIsNone(value(run, "--quality-repeat"))
            else:
                self.assertIsNone(value(run, "--repeat"))
        defaults = {(run["suite"], run["group"]): run for run in dry_run("--suites", "2k")}
        self.assertEqual(value(defaults[("2k", "nesso")], "--repeat"), "3")
        self.assertEqual(value(defaults[("2k", "xerj-neural")], "--quality-repeat"), "3")
        done = subprocess.run(
            [sys.executable, str(SCRIPT), "--nesso-version", "0.3.1", "--dry-run", "--repeat", "0"],
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("--repeat must be a positive integer", done.stderr)

    def test_merge_takes_only_merged_runs(self) -> None:
        mod = self.mod
        with tempfile.TemporaryDirectory() as temp:
            out = pathlib.Path(temp)
            entries = [
                {"suite": "2k", "report": "raw/2k/nesso.json", "merged": True},
                {"suite": "2k", "report": "raw/2k/nesso-fp32.json", "merged": False},
                {"suite": "2k", "report": None, "merged": True},
            ]
            calls = []
            original = mod.subprocess.run

            def fake_run(argv, **kwargs):
                calls.append(argv)
                return subprocess.CompletedProcess(argv, 0, "", "")

            mod.subprocess.run = fake_run
            try:
                result = mod.merge_suite(mod.SUITES[0], entries, out)
            finally:
                mod.subprocess.run = original
        self.assertEqual(result["inputs"], 1)
        self.assertIn(str(out / "raw/2k/nesso.json"), calls[0])
        self.assertNotIn(str(out / "raw/2k/nesso-fp32.json"), calls[0])

    def test_nesso_runs_with_grep(self) -> None:
        # A nesso-only report is schema 3, which eval-retrieval-merge refuses.
        nesso = next(group for group in self.mod.GROUPS if "nesso" in group.engines)
        self.assertEqual(nesso.engines, ("nesso", "grep"))

    def test_every_suite_has_fetches(self) -> None:
        self.assertEqual(set(self.mod.FETCHES), {suite.name for suite in self.mod.SUITES})
        # Every step is a script that exists, so a typo fails here and not mid-run.
        for steps in self.mod.FETCHES.values():
            for script, *_arguments in steps:
                self.assertTrue((ROOT / "scripts" / script).is_file(), script)

    def test_json_and_bundle_suites(self) -> None:
        mod = self.mod
        suites = {suite.name: suite for suite in mod.SUITES}
        self.assertEqual(suites["json"].dataset, "hdfs-2k-json")
        self.assertEqual([step[0] for step in mod.FETCHES["json"]], ["fetch-loghub", "derive-json"])
        self.assertEqual([step[0] for step in mod.FETCHES["bundle"]], ["fetch-loghub", "build-bundle"])
        out = pathlib.Path("/results/0.3.1")
        groups = {group.name: group for group in mod.GROUPS}
        # The bundle is quality only: eval-retrieval refuses --measure for it.
        bundle = mod.Run(suites["bundle"], groups["nesso"]).command(out, "py", {})
        self.assertNotIn("--measure", bundle)
        self.assertNotIn("--repeat", bundle)
        self.assertEqual(bundle[bundle.index("--dataset") + 1], "support-bundle")
        # xerj's repeated quality runs still apply there.
        repeated = mod.Run(suites["bundle"], groups["xerj-neural"]).command(out, "py", {})
        self.assertEqual(repeated[repeated.index("--quality-repeat") + 1], "3")
        measured = mod.Run(suites["json"], groups["nesso"]).command(out, "py", {})
        self.assertEqual(measured[measured.index("--repeat") + 1], "3")
        self.assertIn("--measure", measured)
        # Thread count changes timings only, so there is no threads-1 run of the bundle; fp32 still applies.
        runs = mod.plan(list(mod.SUITES), list(mod.GROUPS), threads_1=True, fp32=True)
        self.assertNotIn(("bundle", "nesso-threads-1"), [(run.suite.name, run.group.name) for run in runs])
        self.assertIn(("bundle", "nesso-fp32"), [(run.suite.name, run.group.name) for run in runs])
        self.assertIn(("json", "nesso-threads-1"), [(run.suite.name, run.group.name) for run in runs])

    def test_command_arguments(self) -> None:
        mod = self.mod
        out = pathlib.Path("/results/0.3.1")
        suites = {suite.name: suite for suite in mod.SUITES}
        groups = {group.name: group for group in mod.GROUPS}
        full = mod.Run(suites["full-1m"], groups["nesso"]).command(out, "py", {})
        self.assertEqual(full[0], "py")
        self.assertIn("--measure", full)
        self.assertEqual(full[full.index("--log-prefix-lines") + 1], "1000000")
        self.assertEqual(full[full.index("--modes") + 1], mod.NESSO_MODES)
        self.assertEqual(full[full.index("--repeat") + 1], "1")
        self.assertEqual(full[full.index("--out") + 1], "/results/0.3.1/raw/full-1m/nesso.json")
        # Indexes go under build/, not into the results directory.
        workdir = pathlib.Path(full[full.index("--workdir") + 1])
        self.assertEqual(workdir, ROOT / "build" / "scorecard" / "0.3.1" / "full-1m" / "nesso")
        needle = mod.Run(suites["bgl-needle-100k"], groups["xerj-neural"]).command(out, "py", {"XERJ_MODEL_DIR": "/m"})
        self.assertNotIn("--log-prefix-lines", needle)
        self.assertNotIn("--modes", needle)
        self.assertEqual(needle[needle.index("--xerj-model-dir") + 1], "/m")
        self.assertEqual(needle[needle.index("--repeat") + 1], "3")
        # xerj's embedding engines repeat quality scoring as often as the suite repeats its measurements.
        self.assertEqual(needle[needle.index("--quality-repeat") + 1], "3")
        semantic = mod.Run(suites["2k"], groups["xerj-semantic"]).command(out, "py", {})
        self.assertEqual(semantic[semantic.index("--quality-repeat") + 1], "3")
        self.assertNotIn("--quality-repeat", mod.Run(suites["bgl-needle-1m"], groups["xerj-neural"]).command(out, "py", {}))
        self.assertNotIn("--quality-repeat", mod.Run(suites["full-1m"], groups["xerj-neural"]).command(out, "py", {}))
        self.assertNotIn("--quality-repeat", mod.Run(suites["2k"], groups["xerj"]).command(out, "py", {}))

    def test_selection_and_competitors(self) -> None:
        mod = self.mod
        self.assertEqual([suite.name for suite in mod.pick("2k,full-1m", mod.SUITES, "suite")], ["2k", "full-1m"])
        with self.assertRaises(SystemExit) as raised:
            mod.pick("2k,nope", mod.SUITES, "suite")
        self.assertIn("unknown suite 'nope'", str(raised.exception))
        with self.assertRaises(SystemExit):
            mod.pick(" , ", mod.GROUPS, "group")
        # grep and BM25 come from the system; nesso has its own installer.
        self.assertEqual(
            mod.competitor_engines(list(mod.GROUPS)),
            ["ripgrep", "diy-faiss", "opensearch", "opensearch-knn", "xerj", "xerj-neural", "xerj-semantic", "ck", "vecgrep"],
        )


class ScorecardRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_scorecard()

    def test_outcomes(self) -> None:
        outcome = self.mod.outcome
        self.assertEqual(outcome(0, "48G", "", False), "ok")
        self.assertEqual(outcome(124, "48G", "", False), "timeout")
        self.assertEqual(outcome(137, "48G", "", True), "timeout")
        self.assertEqual(outcome(137, "48G", "", False), "out-of-memory (48G)")
        # The harness turns a SIGKILLed child into its own exit 1.
        self.assertEqual(outcome(1, "48G", "error: nesso index failed: exit -9\n", False), "out-of-memory (48G)")
        self.assertEqual(outcome(1, "48G", "Command terminated by signal 9\n", False), "out-of-memory (48G)")
        self.assertEqual(outcome(1, "48G", "error: something else\n", False), "failed (exit 1)")
        # Without a cap, a kill is not attributed to memory.
        self.assertEqual(outcome(1, None, "exit -9", False), "failed (exit 1)")

    def test_systemd_verdict_decides_out_of_memory(self) -> None:
        outcome = self.mod.outcome
        # The kernel kills one process and systemd stops the rest of the scope, so
        # the run exits -15 (or 143), which is not a SIGKILL; the scope says why.
        self.assertEqual(outcome(-15, "3G", "eval-retrieval: ... vecgrep: indexing\n", False, "oom-kill"), "out-of-memory (3G)")
        self.assertEqual(outcome(143, "3G", "", False, "oom-kill"), "out-of-memory (3G)")
        # Without that verdict a SIGTERM is just a failure, and a timeout is still a timeout.
        self.assertEqual(outcome(-15, "3G", "", False, "success"), "failed (exit -15)")
        self.assertEqual(outcome(-15, "3G", "", False, None), "failed (exit -15)")
        # timeout exits 124 when it is SIGTERMed too: a memory kill is not a timeout, a real one is.
        self.assertEqual(outcome(124, "3G", "", False, "oom-kill"), "out-of-memory (3G)")
        self.assertEqual(outcome(124, "3G", "", True, "oom-kill"), "timeout")
        self.assertEqual(outcome(124, "3G", "", False, "success"), "timeout")
        self.assertEqual(outcome(0, "3G", "", False, "oom-kill"), "ok")
        # No cap, no attribution.
        self.assertEqual(outcome(-15, None, "", False, "oom-kill"), "failed (exit -15)")

    def test_wrap_names_the_scope_and_unit_names_are_safe(self) -> None:
        mod = self.mod
        wrapped = mod.wrap(["cmd"], "3G", 1, "scorecard-1-2k-nesso")
        self.assertIn("--unit=scorecard-1-2k-nesso", wrapped)
        self.assertNotIn("--unit", " ".join(mod.wrap(["cmd"], "3G", 1)))
        self.assertNotIn("--unit", " ".join(mod.wrap(["cmd"], None, 1, "x")))
        name = mod.scope_name("bgl-needle-100k", "opensearch-knn")
        self.assertRegex(name, r"^scorecard-\d+-bgl-needle-100k-opensearch-knn$")
        self.assertRegex(mod.scope_name("a b/c", "d_e"), r"^[A-Za-z0-9-]+$")

    def test_scope_result_reads_systemctl(self) -> None:
        mod = self.mod
        original = mod.subprocess.run
        calls = []

        def fake(argv, **kwargs):
            calls.append(argv)
            if "show" in argv:
                # The first answer is a scope that has not settled yet; the second is final.
                state = "deactivating\nResult=success\n" if len(calls) == 1 else "failed\nResult=oom-kill\n"
                return subprocess.CompletedProcess(argv, 0, f"ActiveState={state}", "")
            return subprocess.CompletedProcess(argv, 0, "", "")

        mod.subprocess.run = fake
        try:
            self.assertEqual(mod.scope_result("scorecard-1-x"), "oom-kill")
            mod.reset_scope("scorecard-1-x")
        finally:
            mod.subprocess.run = original
        self.assertEqual(calls[0], ["systemctl", "--user", "show", "scorecard-1-x.scope", "-p", "ActiveState", "-p", "Result"])
        # It waited for the final state, and then reset the unit.
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[2], ["systemctl", "--user", "reset-failed", "scorecard-1-x.scope"])

        def failing(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 1, "", "no such unit")

        mod.subprocess.run = failing
        try:
            self.assertIsNone(mod.scope_result("scorecard-1-x"))
        finally:
            mod.subprocess.run = original

    @unittest.skipUnless(
        shutil.which("systemd-run") and subprocess.run(["systemctl", "--user", "is-active", "default.target"], capture_output=True, check=False).returncode == 0,
        "needs a systemd user manager",
    )
    def test_a_real_capped_scope_reports_oom_kill(self) -> None:
        # A bounded allocation (600 MB) under a 200 MB cap, in a scope with a second process,
        # like the scorecard's `timeout` plus a harness: systemd stops the scope with SIGTERM.
        mod = self.mod
        unit = mod.scope_name("test", "oom")
        allocate = 'b = bytearray(b"x") * (600 * 1024 * 1024)'
        script = f"python3 -c {shlex.quote(allocate)}; rc=$?; sleep 3; exit $rc"
        done = subprocess.run(mod.wrap(["bash", "-c", script], "200M", 1, unit), capture_output=True, check=False, timeout=90)
        try:
            self.assertNotEqual(done.returncode, 0)
            scope = mod.scope_result(unit)
            self.assertEqual(scope, "oom-kill")
            self.assertEqual(mod.outcome(done.returncode, "200M", "", False, scope), "out-of-memory (200M)")
        finally:
            mod.reset_scope(unit)

    def test_wrap(self) -> None:
        wrapped = self.mod.wrap(["cmd"], "48G", 2)
        self.assertEqual(wrapped[:3], ["systemd-run", "--user", "--scope"])
        self.assertIn("MemoryMax=48G", wrapped)
        self.assertIn("MemorySwapMax=0", wrapped)
        self.assertEqual(wrapped[-4:], ["timeout", "--kill-after=60", "7200s", "cmd"])
        self.assertEqual(self.mod.wrap(["cmd"], None, 1), ["timeout", "--kill-after=60", "3600s", "cmd"])

    def test_machine_checks(self) -> None:
        mod = self.mod
        self.assertTrue(mod.is_wsl("Linux version 6.6.114.1-microsoft-standard-WSL2"))
        self.assertFalse(mod.is_wsl("Linux version 6.8.0-generic"))
        self.assertFalse(mod.is_wsl(None))
        self.assertEqual(mod.meminfo_bytes("MemTotal: 2048 kB\nSwapTotal: 0 kB\n", "SwapTotal"), 0)
        self.assertEqual(mod.meminfo_bytes("MemTotal: 2048 kB\n", "MemTotal"), 2048 * 1024)
        self.assertIsNone(mod.meminfo_bytes("", "MemTotal"))
        clean = {"wsl": False, "loadAverage1m": 0.1, "nessoBenchDirty": False}
        mod.check_machine(clean, dev=False)
        for problem, message in (
            ({"wsl": True}, "WSL"),
            ({"loadAverage1m": 3.5}, "load average is 3.5"),
            ({"nessoBenchDirty": True}, "uncommitted changes"),
        ):
            with self.assertRaises(SystemExit) as raised:
                mod.check_machine({**clean, **problem}, dev=False)
            self.assertIn(message, str(raised.exception))
            self.assertIn("--dev", str(raised.exception))
            mod.check_machine({**clean, **problem}, dev=True)

    def test_dry_run_prints_one_line_per_run(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--nesso-version", "v0.3.1", "--dry-run", "--suites", "2k", "--groups", "nesso,bm25"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        rows = [json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual([(row["suite"], row["group"]) for row in rows], [("2k", "nesso"), ("2k", "bm25")])
        self.assertIn("/results/0.3.1/raw/2k/nesso.json", rows[0]["argv"][rows[0]["argv"].index("--out") + 1])


def fake_nesso(directory: pathlib.Path, version: str) -> tuple[pathlib.Path, pathlib.Path]:
    """A stub binary that prints VERSION for -V, and a model directory beside it."""
    binary = directory / "bin" / "nesso"
    binary.parent.mkdir(parents=True)
    binary.write_text(f"#!/bin/sh\necho {shlex.quote(version)}\n", encoding="utf-8")
    binary.chmod(0o755)
    model_dir = directory / "models"
    model_dir.mkdir()
    (model_dir / "model.onnx").write_bytes(b"onnx")
    (model_dir / "vocab.txt").write_text("[PAD]\n", encoding="utf-8")
    return binary, model_dir


class ScorecardNessoBinaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_scorecard()

    def scorecard(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False)

    def test_version_and_binary_are_exclusive_and_the_binary_needs_its_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            binary, model_dir = fake_nesso(pathlib.Path(temp), "0.3.1+gabc")
            for args, message in (
                ([], "exactly one of --nesso-version or --nesso-binary"),
                (["--nesso-version", "0.3.1", "--nesso-binary", str(binary), "--nesso-model-dir", str(model_dir)], "exactly one of"),
                (["--nesso-binary", str(binary)], "--nesso-binary and --nesso-model-dir go together"),
                (["--nesso-version", "0.3.1", "--nesso-model-dir", str(model_dir)], "--nesso-binary and --nesso-model-dir go together"),
                (["--nesso-version", "0.3.1", "--nesso-fp32-model-dir", str(model_dir)], "--nesso-fp32-model-dir goes with --nesso-binary"),
                (["--nesso-binary", str(model_dir / "vocab.txt"), "--nesso-model-dir", str(model_dir)], "is not an executable file"),
                (["--nesso-binary", str(binary), "--nesso-model-dir", temp], "has no model.onnx"),
            ):
                done = self.scorecard(*args, "--dry-run")
                self.assertEqual(done.returncode, 1, args)
                self.assertIn(message, done.stderr, args)

    def test_fp32_with_a_binary_needs_its_model_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            binary, model_dir = fake_nesso(pathlib.Path(temp), "0.3.1+gabc")
            base = ["--nesso-binary", str(binary), "--nesso-model-dir", str(model_dir), "--suites", "2k", "--groups", "nesso", "--dry-run"]
            refused = self.scorecard(*base, "--nesso-fp32")
            self.assertEqual(refused.returncode, 1)
            self.assertIn("--nesso-fp32 with --nesso-binary needs --nesso-fp32-model-dir", refused.stderr)
            done = self.scorecard(*base, "--nesso-fp32", "--nesso-fp32-model-dir", str(model_dir))
        self.assertEqual(done.returncode, 0, done.stderr)
        fp32 = [json.loads(line) for line in done.stdout.splitlines() if json.loads(line)["fp32"]]
        self.assertEqual(len(fp32), 1)
        self.assertEqual(fp32[0]["argv"][fp32[0]["argv"].index("--model-dir") + 1], str(model_dir.resolve()))

    def test_dry_run_shows_the_binary_and_names_out_after_its_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            binary, model_dir = fake_nesso(pathlib.Path(temp), "0.3.1+gb20ff665cbb6")
            done = self.scorecard(
                "--nesso-binary", str(binary), "--nesso-model-dir", str(model_dir),
                "--suites", "2k", "--groups", "nesso", "--nesso-threads-1", "--dry-run",
            )
        self.assertEqual(done.returncode, 0, done.stderr)
        rows = [json.loads(line) for line in done.stdout.splitlines()]
        self.assertEqual([row["group"] for row in rows], ["nesso", "nesso-threads-1"])
        for row in rows:
            self.assertEqual(row["nessoBinary"], str(binary.resolve()))
            self.assertEqual(row["nessoModelDir"], str(model_dir.resolve()))
            self.assertNotIn("nessoVersion", row)
            self.assertEqual(row["argv"][row["argv"].index("--out") + 1], str(ROOT / "results" / "0.3.1+gb20ff665cbb6" / "raw" / "2k" / f"{row['group']}.json"))
        self.assertEqual(rows[1]["threads"], "1")
        release = self.scorecard("--nesso-version", "0.3.1", "--suites", "2k", "--groups", "nesso", "--dry-run")
        self.assertEqual(json.loads(release.stdout.splitlines()[0])["nessoVersion"], "0.3.1")

    def test_out_name_is_a_safe_path_component(self) -> None:
        path_name = self.mod.path_name
        self.assertEqual(path_name("0.3.1+gb20ff665cbb6"), "0.3.1+gb20ff665cbb6")
        self.assertEqual(path_name("nesso 0.4.0-rc.1/dirty"), "nesso_0.4.0-rc.1_dirty")
        self.assertEqual(path_name("../.."), "nesso")
        with tempfile.TemporaryDirectory() as temp:
            binary, model_dir = fake_nesso(pathlib.Path(temp), "nesso 0.4.0/x")
            done = self.scorecard("--nesso-binary", str(binary), "--nesso-model-dir", str(model_dir), "--suites", "2k", "--groups", "nesso", "--dry-run")
        self.assertEqual(done.returncode, 0, done.stderr)
        argv = json.loads(done.stdout.splitlines()[0])["argv"]
        self.assertEqual(pathlib.Path(argv[argv.index("--out") + 1]).parents[2], ROOT / "results" / "nesso_0.4.0_x")

    def test_pinned_versions_come_from_install_nesso(self) -> None:
        self.assertTrue({"0.3.0", "0.3.1"} <= self.mod.pinned_versions())

    def run_main(self, args: list[str], install_version: str = "0.3.1") -> tuple[dict, list[dict]]:
        """Runs main() with the machine, installers, fetches, and runs faked; returns machine.json and run envs."""
        mod = self.mod
        envs: list[dict] = []
        saved = {name: getattr(mod, name) for name in ("machine_info", "install", "execute", "merge_suite", "FETCHES")}
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = pathlib.Path(temp.name)
        release_binary, release_models = fake_nesso(base / "release", install_version)

        def install(script, arguments, env):
            self.assertEqual(script, "install-nesso")
            env.update({"NESSO_BINARY": str(release_binary), "NESSO_MODEL_DIR": str(release_models)})

        def execute(run, out, python, env, memory_max, timeout_hours):
            envs.append(dict(env))
            return {"suite": run.suite.name, "group": run.group.name, "outcome": "ok", "report": None, "merged": run.merged}

        mod.machine_info = lambda out, dev: {"developmentOnly": dev, "wsl": False, "loadAverage1m": 0.0, "nessoBenchDirty": False}
        mod.install = install
        mod.execute = execute
        mod.merge_suite = lambda suite, entries, out: {"suite": suite.name, "merged": None}
        mod.FETCHES = {name: [] for name in mod.FETCHES}
        try:
            code = mod.main([*args, "--out", str(base / "out"), "--suites", "2k", "--groups", "nesso", "--memory-max", "none"])
        finally:
            for name, value in saved.items():
                setattr(mod, name, value)
        self.assertEqual(code, 0)
        machine = json.loads((base / "out" / "machine.json").read_text(encoding="utf-8"))
        return machine, envs

    def test_machine_json_for_a_release(self) -> None:
        machine, envs = self.run_main(["--nesso-version", "0.3.1"])
        self.assertEqual(machine["nessoVersion"], "0.3.1")
        self.assertEqual(machine["nessoSource"], "release")
        self.assertFalse(machine["developmentOnly"])
        self.assertEqual(machine["developmentReasons"], [])
        self.assertEqual(machine["nessoVersionOutput"], "0.3.1")
        self.assertRegex(machine["nessoBinarySha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(machine["nessoModel"]["model_onnx_bytes"], 4)
        self.assertEqual(envs[0]["NESSO_BINARY"], machine["nessoBinary"])

    def test_machine_json_for_a_binary_marks_it_development_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            binary, model_dir = fake_nesso(pathlib.Path(temp), "0.3.1+gb20ff665cbb6")
            expected_sha = hashlib.sha256(binary.read_bytes()).hexdigest()
            machine, envs = self.run_main(["--nesso-binary", str(binary), "--nesso-model-dir", str(model_dir), "--nesso-threads-1"])
        self.assertEqual(machine["nessoSource"], "binary")
        self.assertEqual(machine["nessoVersion"], "0.3.1+gb20ff665cbb6")
        self.assertEqual(machine["nessoVersionOutput"], "0.3.1+gb20ff665cbb6")
        self.assertEqual(machine["nessoBinary"], str(binary.resolve()))
        self.assertEqual(machine["nessoBinarySha256"], expected_sha)
        self.assertEqual(machine["nessoModel"], {
            "dir": "models",
            "model_onnx_bytes": 4,
            "model_onnx_sha256": hashlib.sha256(b"onnx").hexdigest(),
            "vocab_bytes": 6,
            "vocab_sha256": hashlib.sha256(b"[PAD]\n").hexdigest(),
        })
        self.assertTrue(machine["developmentOnly"])
        self.assertEqual(len(machine["developmentReasons"]), 1)
        self.assertIn("built outside a pinned release (0.3.1+gb20ff665cbb6)", machine["developmentReasons"][0])
        # Every run, threads-1 included, gets the binary the way install-nesso exports it.
        self.assertEqual([env.get("NESSO_THREADS") for env in envs], [None, None])
        for env in envs:
            self.assertEqual(env["NESSO_BINARY"], str(binary.resolve()))
            self.assertEqual(env["NESSO_MODEL_DIR"], str(model_dir.resolve()))
            self.assertTrue(env["PATH"].startswith(f"{binary.resolve().parent}:"))

    def test_a_binary_reporting_a_pinned_version_is_not_development_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            binary, model_dir = fake_nesso(pathlib.Path(temp), "0.3.1")
            machine, _envs = self.run_main(["--nesso-binary", str(binary), "--nesso-model-dir", str(model_dir)])
        self.assertEqual(machine["nessoSource"], "binary")
        self.assertFalse(machine["developmentOnly"])
        self.assertEqual(machine["developmentReasons"], [])


if __name__ == "__main__":
    unittest.main()
