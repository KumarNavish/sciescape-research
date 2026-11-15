# SPDX-License-Identifier: Apache-2.0
"""Small local batch receipts and a process-group deadline; never allocates compute.

Completed cases are immutable. Restart with the same identity and output directory
to reuse them; copy that directory out before releasing an ephemeral runtime.
"""
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value):
    return hashlib.sha256(_encoded(value)).hexdigest()


def file_hash(path):
    """Hash a regular file, refusing symlinks and special files."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError(f"not a regular file: {path}")
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        return digest.hexdigest()


def atomic_json(path, value):
    """Flush a complete JSON file and rename it atomically in its directory."""
    path = Path(path)
    payload = _encoded(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError(f"symlink output refused: {path}")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _seal(payload):
    return {"payload": payload, "sha256": _digest(payload)}


def _read_sealed(path):
    if path.is_symlink():
        raise ValueError(f"symlink checkpoint refused: {path}")
    value = json.loads(path.read_text())
    if set(value) != {"payload", "sha256"} or value["sha256"] != _digest(value["payload"]):
        raise ValueError(f"checkpoint checksum mismatch: {path}")
    return value["payload"], value["sha256"]


class BatchCheckpoint:
    """One writer, fixed identity and denominator, atomic per-case completion.

    identity must include input, source and model/config revisions. A mismatching
    or damaged checkpoint fails closed; choosing a new output directory is an
    explicit new experiment. rows.json is derived and can be rebuilt safely.
    """

    def __init__(self, out, identity, case_ids):
        out = Path(out)
        if out.is_symlink():
            raise ValueError("output directory must not be a symlink")
        self.out = out.resolve()
        self.identity = json.loads(_encoded(identity))
        self.case_ids = list(case_ids)
        if (not isinstance(identity, dict) or not self.case_ids
                or any(not isinstance(k, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", k) for k in self.case_ids)
                or len(set(self.case_ids)) != len(self.case_ids)):
            raise ValueError("identity must be a dict and case IDs must be nonempty, safe and unique")
        self.key = _digest(self.identity)
        self.directory = self.out / ".batch-checkpoint"
        self.cases = self.directory / "cases"
        self.manifest = self.directory / "manifest.json"
        self._lock = None
        self._records = {}

    def __enter__(self):
        for folder in (self.out, self.directory, self.cases):
            if folder.is_symlink():
                raise ValueError(f"symlink checkpoint directory refused: {folder}")
            folder.mkdir(exist_ok=True, parents=True)
        fd = os.open(self.directory / "lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        self._lock = os.fdopen(fd, "a+")
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError("another writer owns this batch") from error
            if self.manifest.exists():
                self._state, _ = _read_sealed(self.manifest)
                if (self._state.get("version") != 1 or self._state.get("identity") != self.identity
                        or self._state.get("case_ids") != self.case_ids):
                    raise ValueError("checkpoint identity or planned cases changed; use a new output directory")
            else:
                if list(self.cases.glob("*.json")) or (self.out / "rows.json").exists():
                    raise ValueError("outputs exist without an identity manifest; refusing unsafe reuse")
                self._state = {"version": 1, "identity": self.identity, "case_ids": self.case_ids,
                               "completed": {}, "terminal_reason": None}
                self._save()
            if not isinstance(self._state.get("completed"), dict) or not set(self._state["completed"]).issubset(self.case_ids):
                raise ValueError("invalid completed-case manifest")
            reason = self._state.get("terminal_reason")
            if reason is not None and (not isinstance(reason, str) or not reason):
                raise ValueError("invalid terminal reason")
            for path in self.cases.glob("*.json"):
                if path.stem not in self.case_ids:
                    raise ValueError(f"unexpected checkpoint case: {path.name}")
            for case_id in self.case_ids:
                path = self.cases / f"{case_id}.json"
                if path.exists():
                    record, digest = self._read(case_id)
                    expected = self._state["completed"].get(case_id)
                    if expected is not None and expected != digest:
                        raise ValueError(f"case checksum differs from manifest: {case_id}")
                    self._records[case_id] = record
                    # Recover a completed atomic case whose manifest update was interrupted.
                    self._state["completed"][case_id] = digest
                elif case_id in self._state["completed"]:
                    raise ValueError(f"committed checkpoint is missing: {case_id}")
            if reason == "completed" and not self.complete:
                raise ValueError("completed batch is missing planned cases")
            self._save()
            atomic_json(self.out / "rows.json", self.rows())
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self._lock is not None:
            self._lock.close()
            self._lock = None

    def _active(self):
        if self._lock is None:
            raise RuntimeError("checkpoint must be used inside its context manager")

    def _save(self):
        self._active()
        atomic_json(self.manifest, _seal(self._state))

    def _artifact(self, value):
        value = Path(value)
        path = value if value.is_absolute() else self.out / value
        if ".." in value.parts:
            raise ValueError("invalid artifact path")
        try:
            relative = path.resolve().relative_to(self.out)
        except ValueError as error:
            raise ValueError("artifact escapes batch output") from error
        if not relative.parts or relative.parts[0] == ".batch-checkpoint":
            raise ValueError("invalid artifact path")
        for part in (path, *path.parents):
            # Ancestor aliases outside our output (e.g. macOS /var) are fine;
            # links at or below an artifact itself are not.
            if part.is_symlink():
                raise ValueError(f"symlink artifact refused: {path}")
            if part.resolve() == self.out:
                break
        return path, relative.as_posix()

    def _read(self, case_id):
        record, digest = _read_sealed(self.cases / f"{case_id}.json")
        if record.get("identity") != self.key or record.get("case_id") != case_id or not isinstance(record.get("row"), dict):
            raise ValueError(f"invalid case identity: {case_id}")
        if not isinstance(record.get("artifacts"), dict):
            raise ValueError(f"invalid artifact manifest: {case_id}")
        for name, expected in record["artifacts"].items():
            path, _ = self._artifact(name)
            try:
                actual = file_hash(path)
            except OSError as error:
                raise ValueError(f"committed artifact unavailable: {name}") from error
            if actual != expected:
                raise ValueError(f"artifact checksum mismatch: {name}")
        return record, digest

    @property
    def terminal_reason(self):
        self._active()
        return self._state["terminal_reason"]

    @property
    def complete(self):
        return len(self._records) == len(self.case_ids)

    def get(self, case_id):
        self._active()
        if case_id not in self.case_ids:
            raise KeyError(case_id)
        if case_id not in self._records:
            return None
        record, digest = self._read(case_id)
        if digest != self._state["completed"][case_id]:
            raise ValueError(f"case checksum differs from manifest: {case_id}")
        return record["row"]

    def rows(self):
        self._active()
        return [self.get(k) for k in self.case_ids if k in self._records]

    def commit(self, case_id, row, artifacts=()):
        self._active()
        if case_id not in self.case_ids or case_id in self._records or self.terminal_reason is not None:
            raise ValueError("case is unknown, already completed, or batch is terminal")
        if not isinstance(row, dict):
            raise ValueError("case row must be a JSON object")
        hashes = {}
        for artifact in artifacts:
            path, relative = self._artifact(artifact)
            if relative in hashes:
                raise ValueError("duplicate artifact")
            hashes[relative] = file_hash(path)
        record = {"identity": self.key, "case_id": case_id, "row": row, "artifacts": hashes}
        envelope = _seal(record)
        atomic_json(self.cases / f"{case_id}.json", envelope)
        self._records[case_id] = json.loads(_encoded(record))
        self._state["completed"][case_id] = envelope["sha256"]
        self._save()
        atomic_json(self.out / "rows.json", self.rows())

    def finish(self, reason):
        self._active()
        if not isinstance(reason, str) or not reason:
            raise ValueError("terminal reason must be nonempty")
        if self.terminal_reason is not None and self.terminal_reason != reason:
            raise ValueError("cannot replace a terminal decision")
        if reason == "completed" and not self.complete:
            raise ValueError("cannot complete an unfinished batch")
        self._state["terminal_reason"] = reason
        self._save()


def guard_entrypoint(script, timeout_s, receipt):
    """Call before heavy imports. Parent supervises child; child returns normally.

    SIGINT/SIGTERM, timeout and normal exit all reap the process group. This is
    an execution deadline, not runtime provisioning or billing enforcement.
    Provider termination is still required if this supervisor itself is killed.
    """
    script = str(Path(script).resolve())
    timeout_s = float(timeout_s)
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError("runtime limit must be positive and finite")
    marker = "_SCIESCAPE_BATCH_CHILD"
    if os.environ.get(marker) == script:
        return
    began = time.monotonic()
    process = None
    cancelled = False
    status, code = "failed", 1
    receipt = Path(receipt)
    if receipt.is_symlink() or receipt.parent.is_symlink():
        raise ValueError("guard receipt must not use a symlink")
    receipt.parent.mkdir(parents=True, exist_ok=True)
    guard_lock = os.open(receipt.with_name(f".{receipt.name}.lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(guard_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        os.close(guard_lock)
        raise
    attempt = uuid.uuid4().hex

    def cancel(_number, _frame):
        nonlocal cancelled
        cancelled = True
        # Do not lose the Popen handle if cancellation arrives during creation.
        if process is not None:
            raise KeyboardInterrupt

    previous = {s: signal.signal(s, cancel) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        atomic_json(receipt, {"status": "starting", "timeout_s": timeout_s, "attempt_id": attempt})
        if cancelled:
            raise KeyboardInterrupt
        env = dict(os.environ, **{marker: script})
        process = subprocess.Popen([sys.executable, script, *sys.argv[1:]], env=env, start_new_session=True)
        if cancelled:
            raise KeyboardInterrupt
        try:
            code = process.wait(timeout=max(0, timeout_s - (time.monotonic() - began)))
            status = "completed" if code == 0 else "failed"
        except subprocess.TimeoutExpired:
            status, code = "timed_out", 124
    except KeyboardInterrupt:
        status, code = "cancelled", 130
    finally:
        for number in previous:
            signal.signal(number, signal.SIG_IGN)
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        try:
            atomic_json(receipt, {"status": status, "exit_code": code, "attempt_id": attempt,
                                  "elapsed_s": round(time.monotonic() - began, 4), "timeout_s": timeout_s})
        finally:
            os.close(guard_lock)
            for number, handler in previous.items():
                signal.signal(number, handler)
    raise SystemExit(code if code >= 0 else 128 - code)
