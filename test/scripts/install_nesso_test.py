import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "install-nesso"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, check=False)


def pins() -> dict[str, str]:
    text = SCRIPT.read_text(encoding="utf-8")
    block = re.search(r"declare -A DEB_SHA256=\(\n(.*?)\n\)", text, re.S)
    assert block is not None
    return dict(re.findall(r'\["([^"]+)"\]="([^"]*)"', block.group(1)))


class InstallNessoTest(unittest.TestCase):
    def test_pins_are_sha256_for_both_architectures(self) -> None:
        table = pins()
        self.assertIn("0.3.1/amd64", table)
        versions = {key.split("/")[0] for key in table}
        for version in versions:
            self.assertRegex(version, r"^\d+\.\d+\.\d+$")
            for arch in ("amd64", "arm64"):
                self.assertRegex(table.get(f"{version}/{arch}", ""), r"^[0-9a-f]{64}$", f"{version}/{arch}")
        self.assertEqual(len(table), 2 * len(versions))

    def test_unpinned_version_names_the_pins(self) -> None:
        completed = run("--arch", "amd64", "9.9.9")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("no pin for nesso 9.9.9 on amd64", completed.stderr)
        self.assertIn("0.3.1/amd64", completed.stderr)
        self.assertEqual(completed.stdout, "")

    def test_rejects_bad_arguments(self) -> None:
        for args, message in (
            ((), "scripts/install-nesso [--dest DIR]"),
            (("0.3.1", "0.3.0"), "one VERSION only"),
            (("--frobnicate", "0.3.1"), "unknown option '--frobnicate'"),
            (("--arch", "riscv64", "0.3.1"), "no pin for nesso 0.3.1 on riscv64"),
        ):
            completed = run(*args)
            self.assertEqual(completed.returncode, 2, args)
            self.assertIn(message, completed.stderr)
            self.assertEqual(completed.stdout, "")


if __name__ == "__main__":
    unittest.main()
