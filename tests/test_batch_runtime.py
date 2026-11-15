# SPDX-License-Identifier: Apache-2.0
"""CPU fault injection for resumable batches; no model, GPU or provider is used."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest.mock import patch

# Adapted for this research release: import the unchanged runtime from research/.
RUNTIME_DIR = Path(__file__).resolve().parents[1] / "research"
sys.path.insert(0, str(RUNTIME_DIR))
from batch_runtime import BatchCheckpoint, atomic_json, file_hash  # noqa: E402
import batch_runtime  # noqa: E402


class Checkpoints(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / "results"
        self.identity = {"source": "source-sha", "model": "pinned-model", "input": "input-sha", "seed": 7}

    def checkpoint(self, identity=None, cases=None):
        return BatchCheckpoint(self.out, self.identity if identity is None else identity,
                               ["a", "b", "c"] if cases is None else cases)

    def test_resume_preserves_completed_and_failed_cases_in_planned_order(self):
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            with self.checkpoint() as cp:
                artifact = self.out / "a.bin"
                artifact.write_bytes(b"completed output")
                cp.commit("a", {"tag": "a", "score": 0.2}, [artifact])
                cp.commit("b", {"tag": "b", "failed": "scientific rejection"}, [])
                raise RuntimeError("interrupted")
        with self.checkpoint() as cp:
            self.assertEqual(cp.get("a"), {"tag": "a", "score": 0.2})
            self.assertEqual(cp.get("b"), {"tag": "b", "failed": "scientific rejection"})
            self.assertIsNone(cp.get("c"))
            cp.commit("c", {"tag": "c", "score": 0.9}, [])
            self.assertEqual([r["tag"] for r in cp.rows()], ["a", "b", "c"])
        self.assertEqual(len(json.loads((self.out / "rows.json").read_text())), 3)

    def test_changed_source_model_input_or_config_cannot_reuse_outputs(self):
        with self.checkpoint() as cp:
            cp.commit("a", {"tag": "a"}, [])
        for key in ("source", "model", "input", "seed"):
            changed = dict(self.identity, **{key: "different"})
            with self.subTest(key=key), self.assertRaises((ValueError, RuntimeError)):
                with self.checkpoint(identity=changed):
                    pass
        with self.checkpoint() as cp:
            self.assertEqual(cp.get("a"), {"tag": "a"})

    def test_changed_case_set_cannot_silently_drop_failure_denominator(self):
        with self.checkpoint() as cp:
            cp.commit("a", {"failed": "bad geometry"}, [])
        with self.assertRaises((ValueError, RuntimeError)):
            with self.checkpoint(cases=["a", "b"]):
                pass

    def test_incomplete_batch_keeps_the_full_denominator(self):
        with self.checkpoint() as cp:
            cp.commit("a", {"tag": "a", "failed": "bad geometry"}, [])
            self.assertEqual(cp.case_ids, ["a", "b", "c"])
            self.assertFalse(cp.complete)
            with self.assertRaises((ValueError, RuntimeError)):
                cp.finish("completed")
        with self.checkpoint() as cp:
            self.assertEqual(cp.case_ids, ["a", "b", "c"])
            self.assertFalse(cp.complete)
            self.assertEqual(len(cp.rows()), 1)

    def test_scientific_early_stop_survives_restart(self):
        with self.checkpoint() as cp:
            cp.commit("a", {"tag": "a", "failed": "bad geometry"}, [])
            cp.finish("first cases rejected the mechanism")
        with self.checkpoint() as cp:
            self.assertEqual(cp.terminal_reason, "first cases rejected the mechanism")
            self.assertIsNone(cp.get("b"))
            self.assertFalse(cp.complete)
            with self.assertRaises((ValueError, RuntimeError)):
                cp.commit("b", {"tag": "b", "score": 0.9}, [])

    def test_corrupt_case_and_manifest_are_not_silently_recreated(self):
        for relative in (".batch-checkpoint/cases/a.json", ".batch-checkpoint/manifest.json"):
            with self.subTest(relative=relative):
                self.out = self.root / relative.replace("/", "_")
                with self.checkpoint() as cp:
                    cp.commit("a", {"tag": "a"}, [])
                corrupt = self.out / relative
                corrupt.write_text("{truncated")
                with self.assertRaises((ValueError, RuntimeError)):
                    with self.checkpoint() as cp:
                        cp.get("a")
                self.assertEqual(corrupt.read_text(), "{truncated")

    def test_valid_json_with_a_modified_row_fails_its_checksum(self):
        with self.checkpoint() as cp:
            cp.commit("a", {"tag": "a", "score": 0.2}, [])
        case = self.out / ".batch-checkpoint" / "cases" / "a.json"
        text = case.read_text()
        self.assertIn("0.2", text)
        case.write_text(text.replace("0.2", "0.9"))
        with self.assertRaises((ValueError, RuntimeError)):
            with self.checkpoint() as cp:
                cp.get("a")

    def test_invalid_or_duplicate_case_ids_fail_before_any_work(self):
        for cases in (["a", "a"], ["../escape"], ["/absolute"], [""], ["a/b"]):
            with self.subTest(cases=cases), self.assertRaises((ValueError, RuntimeError)):
                with self.checkpoint(cases=cases):
                    pass

    def test_artifact_mutation_is_not_a_cache_hit(self):
        with self.checkpoint() as cp:
            artifact = self.out / "a.bin"
            artifact.write_bytes(b"first")
            cp.commit("a", {"tag": "a"}, [artifact])
        artifact.write_bytes(b"changed")
        with self.assertRaises((ValueError, RuntimeError)):
            with self.checkpoint() as cp:
                cp.get("a")

    def test_missing_artifact_is_not_a_cache_hit(self):
        with self.checkpoint() as cp:
            artifact = self.out / "a.bin"
            artifact.write_bytes(b"first")
            cp.commit("a", {"tag": "a"}, [artifact])
        artifact.unlink()
        with self.assertRaises((ValueError, RuntimeError, OSError)):
            with self.checkpoint() as cp:
                cp.get("a")

    def test_atomic_case_survives_interrupted_manifest_update(self):
        with self.checkpoint() as cp:
            original = batch_runtime.atomic_json

            def interrupted(path, value):
                if Path(path) == cp.manifest:
                    raise OSError("disk unavailable after atomic case write")
                return original(path, value)

            with patch.object(batch_runtime, "atomic_json", side_effect=interrupted):
                with self.assertRaisesRegex(OSError, "disk unavailable"):
                    cp.commit("a", {"tag": "a"}, [])
        with self.checkpoint() as cp:
            self.assertEqual(cp.get("a"), {"tag": "a"})
            self.assertEqual(cp.rows(), [{"tag": "a"}])

    def test_rows_reject_artifact_corruption_during_live_context(self):
        with self.checkpoint() as cp:
            artifact = self.out / "a.bin"
            artifact.write_bytes(b"initial output")
            cp.commit("a", {"tag": "a"}, [artifact])
            artifact.write_bytes(b"changed after commit")
            with self.assertRaises((ValueError, RuntimeError)):
                cp.rows()

    def test_external_and_symlink_artifacts_are_refused(self):
        outside = self.root / "outside.bin"
        outside.write_bytes(b"not owned by this batch")
        with self.checkpoint() as cp:
            with self.assertRaises((ValueError, RuntimeError)):
                cp.commit("a", {"tag": "a"}, [outside])
            link = self.out / "linked.bin"
            link.symlink_to(outside)
            with self.assertRaises((ValueError, RuntimeError)):
                cp.commit("a", {"tag": "a"}, [link])
            self.assertIsNone(cp.get("a"))

    def test_live_writer_blocks_a_second_process(self):
        code = "from batch_runtime import BatchCheckpoint\nwith BatchCheckpoint(__import__('pathlib').Path(__import__('sys').argv[1]), {'source':'source-sha','model':'pinned-model','input':'input-sha','seed':7}, ['a','b','c']): pass\n"
        with self.checkpoint():
            result = subprocess.run([sys.executable, "-c", code, str(self.out)],
                                    env={**os.environ, "PYTHONPATH": str(RUNTIME_DIR)},
                                    capture_output=True, text=True, timeout=4)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        with self.checkpoint() as cp:
            self.assertEqual(cp.rows(), [])

    def test_process_crash_then_restart_executes_each_case_only_once(self):
        trace = self.root / "executed.txt"
        code = ("import os\nfrom pathlib import Path\nfrom batch_runtime import BatchCheckpoint\n"
                f"with BatchCheckpoint(Path({str(self.out)!r}), {self.identity!r}, ['a','b','c']) as cp:\n"
                " for tag in cp.case_ids:\n"
                "  if cp.get(tag) is not None: continue\n"
                f"  with Path({str(trace)!r}).open('a') as f: f.write(tag + '\\n')\n"
                "  cp.commit(tag, {'tag':tag}, [])\n"
                "  if tag == 'a': os._exit(77)\n"
                " cp.finish('completed')\n")
        env = {**os.environ, "PYTHONPATH": str(RUNTIME_DIR)}
        first = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=4)
        self.assertEqual(first.returncode, 77, first.stderr)
        second = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=4)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(trace.read_text().splitlines(), ["a", "b", "c"])
        with self.checkpoint() as cp:
            self.assertTrue(cp.complete)
            self.assertEqual(cp.terminal_reason, "completed")

    def test_atomic_json_and_file_hash_round_trip(self):
        destination = self.root / "value.json"
        atomic_json(destination, {"status": "one"})
        first = file_hash(destination)
        atomic_json(destination, {"status": "two"})
        self.assertEqual(json.loads(destination.read_text()), {"status": "two"})
        self.assertNotEqual(file_hash(destination), first)


class Deadlines(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def script(self, body, seconds=0.8):
        script = self.root / "job.py"
        receipt = self.root / "receipt.json"
        prefix = ("import sys\nfrom pathlib import Path\n"
                  f"sys.path.insert(0, {str(RUNTIME_DIR)!r})\n"
                  "from batch_runtime import guard_entrypoint\n"
                  f"guard_entrypoint(__file__, {seconds!r}, Path({str(receipt)!r}))\n")
        script.write_text(prefix + textwrap.dedent(body))
        return script, receipt

    def run_script(self, script):
        started = time.monotonic()
        result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=6)
        return result, time.monotonic() - started

    def test_success_and_nonzero_exit_are_preserved(self):
        for exit_code in (0, 7):
            with self.subTest(exit_code=exit_code):
                script, receipt = self.script(f"print('output stays visible', flush=True)\nraise SystemExit({exit_code})\n")
                result, _ = self.run_script(script)
                self.assertEqual(result.returncode, exit_code, result.stderr)
                self.assertIn("output stays visible", result.stdout)
                self.assertIsInstance(json.loads(receipt.read_text()), dict)

    def test_deadline_covers_imports_and_model_loading(self):
        (self.root / "slow_import.py").write_text("import time\ntime.sleep(30)\n")
        script, receipt = self.script("import slow_import\n")
        result, elapsed = self.run_script(script)
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertLess(elapsed, 4)
        self.assertTrue(receipt.is_file())

    def test_continuous_output_does_not_extend_deadline_and_child_is_killed(self):
        heartbeat = self.root / "heartbeat"
        pidfile = self.root / "child.pid"
        child = ("import os,signal,time\nfrom pathlib import Path\n"
                 "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                 f"Path({str(pidfile)!r}).write_text(str(os.getpid()))\n"
                 "while True:\n"
                 f" Path({str(heartbeat)!r}).write_text(str(time.monotonic()))\n"
                 " time.sleep(0.03)\n")
        script, receipt = self.script(
            "import subprocess,time\n"
            f"subprocess.Popen([sys.executable, '-c', {child!r}])\n"
            "while True:\n print('still busy', flush=True)\n time.sleep(0.03)\n", seconds=1)
        result, elapsed = self.run_script(script)
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertGreater(result.stdout.count("still busy"), 2)
        self.assertLess(elapsed, 4)
        self.assertTrue(receipt.is_file())
        pid = int(pidfile.read_text())
        final = heartbeat.read_text()
        time.sleep(0.15)
        self.assertEqual(heartbeat.read_text(), final)
        state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=2)
        self.assertTrue(not state.stdout.strip() or state.stdout.strip().startswith("Z"), state.stdout)

    def test_termination_of_supervisor_cleans_up_the_worker(self):
        marker = self.root / "worker.pid"
        script, receipt = self.script(
            "import os,time\n"
            f"Path({str(marker)!r}).write_text(str(os.getpid()))\n"
            "while True: time.sleep(0.03)\n", seconds=30)
        process = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, text=True)
        try:
            limit = time.monotonic() + 3
            while not marker.exists() and time.monotonic() < limit:
                time.sleep(0.01)
            self.assertTrue(marker.exists(), "guarded worker did not start")
            pid = int(marker.read_text())
            process.send_signal(signal.SIGTERM)
            _, stderr = process.communicate(timeout=4)
            self.assertEqual(process.returncode, 130, stderr)
            self.assertTrue(receipt.is_file())
            state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=2)
            self.assertTrue(not state.stdout.strip() or state.stdout.strip().startswith("Z"), state.stdout)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)

    def test_second_supervisor_refuses_without_overwriting_active_receipt(self):
        starts = self.root / "starts"
        script, receipt = self.script(
            "import os,time\n"
            f"with Path({str(starts)!r}).open('a') as f: f.write(str(os.getpid()) + '\\n')\n"
            "while True: time.sleep(0.03)\n", seconds=30)
        first = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.PIPE, text=True)
        try:
            limit = time.monotonic() + 3
            while not starts.exists() and time.monotonic() < limit:
                time.sleep(0.01)
            self.assertTrue(starts.exists(), "first worker did not start")
            initial = json.loads(receipt.read_text())
            second, _ = self.run_script(script)
            self.assertNotEqual(second.returncode, 0, second.stdout)
            self.assertEqual(json.loads(receipt.read_text()), initial)
            self.assertEqual(len(starts.read_text().splitlines()), 1)
            self.assertIsNone(first.poll())
        finally:
            if first.poll() is None:
                first.send_signal(signal.SIGTERM)
                first.communicate(timeout=4)

    def test_successful_parent_also_reaps_its_leftover_child(self):
        heartbeat = self.root / "orphan-heartbeat"
        pidfile = self.root / "orphan.pid"
        child = ("import os,time\nfrom pathlib import Path\n"
                 f"Path({str(pidfile)!r}).write_text(str(os.getpid()))\n"
                 "while True:\n"
                 f" Path({str(heartbeat)!r}).write_text(str(time.monotonic()))\n"
                 " time.sleep(0.02)\n")
        script, receipt = self.script(
            "import subprocess,time\n"
            f"subprocess.Popen([sys.executable, '-c', {child!r}])\n"
            f"while not Path({str(heartbeat)!r}).exists(): time.sleep(0.01)\n", seconds=3)
        result, elapsed = self.run_script(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(elapsed, 4)
        self.assertTrue(receipt.is_file())
        pid = int(pidfile.read_text())
        final = heartbeat.read_text()
        time.sleep(0.1)
        self.assertEqual(heartbeat.read_text(), final)
        state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=2)
        self.assertTrue(not state.stdout.strip() or state.stdout.strip().startswith("Z"), state.stdout)

    def test_invalid_deadlines_never_run_the_child(self):
        for seconds in (0, -1, float("inf"), float("nan")):
            with self.subTest(seconds=seconds):
                # A string expression represents non-finite values faithfully in the fixture.
                value = seconds if seconds in (0, -1) else f"float('{seconds}')"
                script, _ = self.script("raise AssertionError('child ran')\n", seconds=value)
                if isinstance(value, str):
                    script.write_text(script.read_text().replace(repr(value), value))
                result, elapsed = self.run_script(script)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("child ran", result.stderr)
                self.assertLess(elapsed, 3)


if __name__ == "__main__":
    unittest.main()
