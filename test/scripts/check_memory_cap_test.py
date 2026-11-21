import os
import pathlib
import stat
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check-memory-cap"


def shim(directory: pathlib.Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def run_script(codes: list[int], *args: str) -> tuple[subprocess.CompletedProcess[str], pathlib.Path]:
    """Run the check with a stand-in systemd-run that exits with `codes` in turn, and stand-ins for sudo."""
    directory = pathlib.Path(tempfile.mkdtemp())
    counter = directory / "count"
    counter.write_text("0", encoding="utf-8")
    shim(
        directory,
        "systemd-run",
        f'n=$(<{counter}); echo $((n + 1)) > {counter}\ncodes=({" ".join(map(str, codes))})\n'
        f'idx=$n; (( idx >= ${{#codes[@]}} )) && idx=$(( ${{#codes[@]}} - 1 ))\nexit "${{codes[$idx]}}"\n',
    )
    for name in ("sudo", "loginctl", "systemctl"):
        shim(directory, name, f'echo "{name} $*" >> {directory}/calls\nexit 0\n')
    env = {**os.environ, "PATH": f"{directory}:{os.environ['PATH']}"}
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, check=False, env=env), directory


class CheckMemoryCapTest(unittest.TestCase):
    def test_a_killed_probe_means_the_cap_works(self) -> None:
        done, directory = run_script([137])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("probe 1: exit 137 (enforced)", done.stdout)
        self.assertIn("ok: a 100 MB cap killed a 400 MB allocation", done.stdout)
        calls = (directory / "calls").read_text(encoding="utf-8") if (directory / "calls").exists() else ""
        self.assertNotIn("sudo", calls, "no fix needed when the cap works")

    def test_a_finished_probe_means_the_cap_is_not_enforced(self) -> None:
        done, _directory = run_script([0])
        self.assertEqual(done.returncode, 1)
        self.assertIn("(not-enforced)", done.stdout)
        self.assertIn("the cap is not enforced", done.stderr)
        self.assertIn("memory controller", done.stderr)

    def test_missing_user_manager_is_fixed_once_and_probed_again(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env_file = pathlib.Path(temp) / "env"
            done, directory = run_script([1, 137], "--env-file", str(env_file))
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertIn("probe 1: exit 1 (unavailable)", done.stdout)
            self.assertIn("probe 2: exit 137 (enforced)", done.stdout)
            calls = (directory / "calls").read_text(encoding="utf-8")
            self.assertIn("sudo loginctl enable-linger", calls)
            self.assertIn("sudo systemctl start user@", calls)
            # Later steps of a CI job inherit the session variables.
            text = env_file.read_text(encoding="utf-8")
            self.assertIn("XDG_RUNTIME_DIR=/run/user/", text)
            self.assertIn("DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/", text)

    def test_still_unavailable_after_the_fix_fails_with_an_explanation(self) -> None:
        done, _directory = run_script([1])
        self.assertEqual(done.returncode, 1)
        self.assertIn("probe 2: exit 1 (unavailable)", done.stdout)
        self.assertIn("systemd-run --user does not work here, even after enabling lingering", done.stderr)

    def test_without_an_env_file_the_variables_are_printed(self) -> None:
        done, _directory = run_script([1, 137])
        self.assertIn("export XDG_RUNTIME_DIR=/run/user/", done.stdout)

    def test_unknown_argument(self) -> None:
        done = subprocess.run(["bash", str(SCRIPT), "--nope"], capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 2)
        self.assertIn("unknown argument", done.stderr)


if __name__ == "__main__":
    unittest.main()
