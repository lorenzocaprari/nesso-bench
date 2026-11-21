import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "install-competitors"
WORKFLOW = ROOT / ".github" / "workflows" / "eval-competitors.yml"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, check=False)


class InstallCompetitorsTest(unittest.TestCase):
    def test_dry_run_maps_engines_to_pieces(self) -> None:
        cases = {
            ("diy-faiss",): ["diy"],
            ("opensearch",): ["opensearch"],
            ("opensearch-knn",): ["diy", "opensearch"],
            ("ck",): ["ck"],
            ("vecgrep",): ["vecgrep"],
            ("xerj",): ["xerj"],
            ("xerj-semantic",): ["xerj"],
            ("xerj-neural",): ["xerj", "minilm"],
            # Install order is fixed and a piece is listed once.
            ("xerj-neural", "diy-faiss", "xerj"): ["diy", "xerj", "minilm"],
            ("ripgrep",): ["ripgrep"],
            ("all",): ["diy", "opensearch", "ck", "vecgrep", "xerj", "minilm", "ripgrep"],
        }
        for engines, pieces in cases.items():
            completed = run("--dry-run", *engines)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout.split(), pieces, engines)

    def test_rejects_unknown_engines_and_options(self) -> None:
        for args, message in (
            (("--dry-run", "ck", "nope"), "unknown engine 'nope'"),
            (("--dry-run", "grep"), "unknown engine 'grep'"),
            (("--frobnicate", "ck"), "unknown option '--frobnicate'"),
        ):
            completed = run(*args)
            self.assertEqual(completed.returncode, 2, args)
            self.assertIn(message, completed.stderr)
            self.assertEqual(completed.stdout, "")

    def test_no_engine_prints_usage(self) -> None:
        completed = run()
        self.assertEqual(completed.returncode, 2)
        self.assertIn("scripts/install-competitors [--dest DIR]", completed.stderr)

    def test_every_piece_has_an_installer(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        pieces = re.search(r"^PIECES=\(([^)]*)\)", text, re.M)
        assert pieces is not None
        for piece in pieces.group(1).split():
            self.assertRegex(text, rf"(?m)^install_{piece}\(\) \{{", piece)

    def test_pins_live_only_in_the_script(self) -> None:
        # The workflow installs through the script; a digest copied back into
        # it would drift from the one the script checks. Action pins are
        # 40-hex commits; sha256 and sha512 digests are 64 and 128 hex.
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\b[0-9a-f]{64,}\b", workflow))
        self.assertIn("scripts/install-competitors", workflow)
        for name in ("CK_SHA256", "XERJ_SHA256", "OPENSEARCH_SHA512", "MINILM_MODEL_SHA256", "VECGREP_REV", "RIPGREP_SHA256"):
            self.assertNotIn(name, workflow)


if __name__ == "__main__":
    unittest.main()
