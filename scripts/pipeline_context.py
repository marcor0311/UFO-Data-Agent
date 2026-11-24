"""Shared execution context of one pipeline invocation (no Gold or Silver logic).

Every data script hashes files through :func:`digest` and runs the full Silver
acceptance through :func:`silver_acceptance`, so a single ``build_all.py`` run
reads each stable file once and accepts each exact Silver once, however many
steps reuse it. The context lives in memory only: a new process starts empty
and verifies again everything it reuses.

It also records what a run costs: duration per phase, every full hash read
(path, bytes, seconds) and how many Silver acceptances actually ran.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import time

BLOCK = 4 * 1024 * 1024


def _stat_key(path: Path) -> tuple:
    st = path.stat()
    return (str(path), st.st_ino, st.st_size, st.st_mtime_ns)


class RunContext:
    def __init__(self):
        self._digests: dict = {}
        self._acceptance: dict = {}
        self.hash_reads: list[dict] = []
        self.phases: list[dict] = []
        self.acceptance_runs = 0
        # Tests replace the official Silver acceptance with a fixture gate.
        self.acceptance_override = None

    # -- hashes ---------------------------------------------------------
    def digest(self, path) -> str:
        """SHA-256 of a file, read once while its identity and stat are unchanged.

        The key is (path, inode, size, mtime_ns), taken before and after the
        read: a file that changes while it is hashed is never memoised, and any
        later write changes the key and forces a fresh read.
        """
        path = Path(path).resolve()
        key = _stat_key(path)
        if key in self._digests:
            return self._digests[key]
        began = time.monotonic()
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(BLOCK), b""):
                h.update(block)
        value = h.hexdigest()
        self.hash_reads.append({"path": str(path), "bytes": key[2], "seconds": round(time.monotonic() - began, 3)})
        if _stat_key(path) == key:
            self._digests[key] = value
        return value

    def replace(self, source, target) -> None:
        """os.replace that keeps a memoised hash: a rename does not change the bytes.

        The hash moves to the new path only if inode, size and mtime are the
        same after the rename; otherwise the next digest reads the file again.
        """
        source, target = Path(source).resolve(), Path(target).resolve()
        before = _stat_key(source)
        value = self._digests.get(before)
        os.replace(source, target)
        if value is not None:
            after = _stat_key(target)
            if after[1:] == before[1:]:
                self._digests[after] = value

    # -- Silver acceptance ----------------------------------------------
    def silver_acceptance(self, silver, bronze, compute):
        """Full Silver acceptance once per exact (Silver SHA, Bronze SHA)."""
        key = (self.digest(silver), self.digest(bronze))
        if key not in self._acceptance:
            run = self.acceptance_override or compute
            self.acceptance_runs += 1
            self._acceptance[key] = run(Path(silver), Path(bronze))
        return self._acceptance[key]

    # -- measurements ---------------------------------------------------
    @contextmanager
    def phase(self, name: str):
        entry = {"phase": name, "status": "running", "seconds": None}
        self.phases.append(entry)
        began = time.monotonic()
        try:
            yield entry
            entry["status"] = "ok"
        except BaseException:
            entry["status"] = "failed"
            raise
        finally:
            entry["seconds"] = round(time.monotonic() - began, 2)

    def summary(self) -> dict:
        per_file = Counter(r["path"] for r in self.hash_reads)
        return {"phases": list(self.phases),
                "hash_reads": {"count": len(self.hash_reads), "bytes": sum(r["bytes"] for r in self.hash_reads),
                               "seconds": round(sum(r["seconds"] for r in self.hash_reads), 2),
                               "repeated_files": {p: n for p, n in per_file.items() if n > 1},
                               "reads": list(self.hash_reads)},
                "silver_acceptance_runs": self.acceptance_runs}


CONTEXT = RunContext()


def reset() -> RunContext:
    """Start a new invocation: forget every hash and acceptance."""
    global CONTEXT
    CONTEXT = RunContext()
    return CONTEXT


def current() -> RunContext:
    return CONTEXT


def digest(path) -> str:
    return CONTEXT.digest(path)


def silver_acceptance(silver, bronze, compute):
    return CONTEXT.silver_acceptance(silver, bronze, compute)


def replace(source, target) -> None:
    CONTEXT.replace(source, target)


def text_digest_file(path) -> str:
    """SHA-256 of a text file with CRLF normalised to LF.

    Used for code, policies and references that enter a fingerprint (Silver
    run_id, Gold definitions): a Windows checkout with CRLF endings produces
    the same fingerprint as macOS or Linux.
    """
    data = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def write_text(path, text: str) -> None:
    """UTF-8 with LF endings on every platform."""
    Path(path).write_text(text, encoding="utf-8", newline="\n")
