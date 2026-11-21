import csv
import gzip
import importlib.machinery
import importlib.util
import json
import pathlib
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILD = ROOT / "scripts" / "build-bundle"
EVAL = ROOT / "scripts" / "eval-retrieval"


def load(path: pathlib.Path, name: str):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def fake_samples(bench: pathlib.Path, module) -> dict[str, list[str]]:
    """A three-line log and event labels for every source the builder reads."""
    bench.mkdir(parents=True)
    lines_by_system = {}
    for source in module.SOURCES:
        lines = [f"{source.system} line {n}" for n in range(1, 4)]
        (bench / source.sample).write_text("\n".join(lines) + "\n", encoding="utf-8")
        with (bench / f"{source.sample}_structured.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["LineId", "EventId"])
            for number in range(1, 4):
                writer.writerow([number, f"E{number}"])
        lines_by_system[source.system] = lines
    return lines_by_system


class BuildBundleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load(BUILD, "build_bundle")

    def build(self, directory: pathlib.Path) -> tuple[dict, dict[str, list[str]], pathlib.Path]:
        bench = directory / "bench"
        self.mod.BENCH_DIR = bench
        samples = fake_samples(bench, self.mod)
        out = bench / "bundle"
        out.mkdir()
        return self.mod.build(out), samples, out

    def test_every_container_holds_its_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, samples, out = self.build(pathlib.Path(temp))
            tree = out / "bundle"
            self.assertEqual(
                gzip.decompress((tree / "var/log/secure-20051210.gz").read_bytes()).decode().splitlines(), samples["openssh"]
            )
            self.assertEqual((tree / "var/log/messages").read_text().splitlines(), samples["linux"])
            self.assertEqual((tree / "var/log/hdfs/datanode.log.1").read_text().splitlines(), samples["hdfs"])
            with tarfile.open(tree / "sos_reports/bgl-ras.tar") as archive:
                self.assertEqual(archive.getnames(), ["var/log/bgl/ras.log"])
                self.assertEqual(archive.extractfile("var/log/bgl/ras.log").read().decode().splitlines(), samples["bgl"])
            with tarfile.open(tree / "sos_reports/thunderbird.tgz", "r:gz") as archive:
                self.assertEqual(archive.extractfile("var/log/thunderbird/syslog").read().decode().splitlines(), samples["thunderbird"])
            with zipfile.ZipFile(tree / "var/log/httpd/error_log.zip") as archive:
                self.assertEqual(archive.read("error_log").decode().splitlines(), samples["apache"])
        self.assertEqual([entry["container"] for entry in manifest["sources"]], ["tar", "tgz", "plain", "zip", "plain", "gz"])

    def test_manifest_and_concatenated_log_agree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, samples, out = self.build(pathlib.Path(temp))
            concat = (out.parent / "SupportBundle_concat.log").read_text().splitlines()
            with (out.parent / "SupportBundle_concat.log_structured.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
        # Visiting order is nesso's: files by byte order of the path.
        paths = [entry["path"] for entry in manifest["sources"]]
        self.assertEqual(paths, sorted(paths, key=str.encode))
        self.assertEqual(manifest["totalLines"], len(concat))
        self.assertEqual(len(rows), len(concat))
        offset = 0
        for entry in manifest["sources"]:
            self.assertEqual(entry["lineOffset"], offset)
            self.assertEqual(concat[offset : offset + entry["lineCount"]], samples[entry["system"]])
            offset += entry["lineCount"]
        # Event ids carry their system, so two systems' E1 stay apart.
        self.assertEqual(rows[0], {"LineId": "1", "EventId": "bgl:E1"})
        self.assertEqual({row["EventId"] for row in rows if row["EventId"].endswith(":E1")}, {f"{s}:E1" for s in samples})
        # nesso names an archive member `path:member`, and a plain or gz file by its path.
        sources = {entry["system"]: entry["source"] for entry in manifest["sources"]}
        self.assertEqual(sources["bgl"], "bundle/sos_reports/bgl-ras.tar:var/log/bgl/ras.log")
        self.assertEqual(sources["linux"], "bundle/var/log/messages")
        self.assertEqual(sources["openssh"], "bundle/var/log/secure-20051210.gz")

    def test_build_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first, _samples, out = self.build(pathlib.Path(temp))
            tree = {path.relative_to(out): path.read_bytes() for path in sorted(out.rglob("*")) if path.is_file()}
            second = self.mod.build(out)
            again = {path.relative_to(out): path.read_bytes() for path in sorted(out.rglob("*")) if path.is_file()}
        self.assertEqual(first, second)
        self.assertEqual(tree, again)

    def test_missing_sample_names_the_fix(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self.mod.BENCH_DIR = pathlib.Path(temp) / "empty"
            with self.assertRaises(SystemExit) as raised:
                self.mod.build(pathlib.Path(temp) / "out")
        self.assertIn("fetch-loghub", str(raised.exception))


class SupportBundleEngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load(EVAL, "eval_retrieval_bundle")

    def manifest(self, directory: pathlib.Path) -> pathlib.Path:
        (directory / "manifest.json").write_text(
            json.dumps(
                {
                    "sources": [
                        {"source": "bundle/a.tar:x.log", "lineOffset": 0, "lineCount": 3},
                        {"source": "bundle/b.log", "lineOffset": 3, "lineCount": 2},
                    ]
                }
            ),
            encoding="utf-8",
        )
        return directory

    def test_hits_map_to_concatenated_line_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            bundle = self.mod.SupportBundle.load(self.manifest(pathlib.Path(temp)))
        self.assertEqual(bundle.line_id({"source": "bundle/a.tar:x.log", "line": 2}), 2)
        self.assertEqual(bundle.line_id({"source": "bundle/b.log", "line": 1}), 4)
        for hit, message in (
            ({"source": "bundle/other.log", "line": 1}, "not in the bundle manifest"),
            ({"source": "bundle/b.log", "line": 3}, "has 2 lines in the manifest"),
            ({"source": "bundle/b.log", "line": 0}, "has 2 lines in the manifest"),
        ):
            with self.assertRaises(SystemExit) as raised:
                bundle.line_id(hit)
            self.assertIn(message, str(raised.exception))

    def test_missing_manifest_names_the_fix(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(SystemExit) as raised:
                self.mod.SupportBundle.load(pathlib.Path(temp))
        self.assertIn("scripts/build-bundle", str(raised.exception))

    def test_nesso_indexes_the_directory_from_its_parent_and_maps_hits(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = pathlib.Path(temp)
            (directory / "bundle-root").mkdir()
            root = self.manifest(directory / "bundle-root")
            log = directory / "calls.log"
            fake = directory / "nesso"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                f'echo "$PWD|$*" >> {log}\n'
                'if [[ "$1" == search ]]; then\n'
                '  echo \'{"rank":1,"source":"bundle/b.log","kind":"line","line":2,"text":"x"}\'\n'
                '  echo \'{"rank":2,"source":"bundle/a.tar:x.log","kind":"line","line":1,"text":"y"}\'\n'
                "fi\n",
                encoding="utf-8",
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            engine = self.mod.NessoEngine(
                binary=fake, model_dir=directory, corpus=directory / "work" / "c.nesso", bundle=self.mod.SupportBundle.load(root)
            )
            engine.prepare(directory / "concat.log", ["ignored"], directory / "work")
            ranked = engine.rank_mode("q", "auto")
            calls = log.read_text().splitlines()
        # Indexed as `bundle` from the bundle's parent directory, so sources are named as in the manifest.
        self.assertTrue(calls[0].startswith(f"{root.resolve()}|index -o "), calls[0])
        self.assertIn(" bundle --model-dir ", calls[0])
        self.assertEqual(ranked, [5, 1])

    def test_dataset_selection_and_refusals(self) -> None:
        mod = self.mod
        self.assertEqual([spec.name for spec in mod.parse_datasets("support-bundle")], ["support-bundle"])
        with self.assertRaises(SystemExit) as raised:
            mod.parse_datasets("support-bundle,hdfs-2k")
        self.assertIn("cannot be mixed", str(raised.exception))
        for extra in (["--measure"], ["--measure", "--log-prefix-lines", "100"]):
            done = subprocess.run(
                [sys.executable, str(EVAL), "--dataset", "support-bundle", "--engine", "grep", *extra, "--out", "/dev/null"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(done.returncode, 0, extra)
            self.assertIn("scores quality only", done.stderr)

    def test_committed_queries_validate_against_the_built_bundle(self) -> None:
        mod = self.mod
        spec = mod.BUNDLE_SPEC
        queries = mod.load_queries(spec.queries_path)
        classes = {name: sum(query.class_name == name for query in queries) for name in ("exact_id", "paraphrase", "cause")}
        self.assertEqual(classes, {"exact_id": 18, "paraphrase": 18, "cause": 18})
        self.assertEqual(sum(query.split == "test" for query in queries), 18)
        if not (spec.log_path.is_file() and spec.structured_path.is_file()):
            self.skipTest("support bundle not built")
        lines = mod.read_log_lines(spec.log_path)
        events = mod.load_event_ids(spec.structured_path)
        mod.assert_line_id_alignment(spec.log_path, events, lines)
        mod.validate_relevant_lines(queries, spec.log_path, lines)
        mod.validate_relevant_events(queries, events, spec.structured_path)


if __name__ == "__main__":
    unittest.main()
