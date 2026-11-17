"""Exercise maintenance failure behavior without touching Docker or real data."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "production_operations", Path(__file__).parents[2] / "scripts" / "production.py"
)
operations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operations)


def test_backup_failure_resumes_only_previously_running_writers(monkeypatch):
    production = operations.Production.__new__(operations.Production)
    calls = []

    def compose(*args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess([], 0, stdout=b"db\nbackend\n")

    def fail():
        raise OSError("backup disk unavailable")

    monkeypatch.setattr(production, "compose", compose)
    monkeypatch.setattr(production, "snapshot", fail)
    with pytest.raises(OSError):
        production.backup()
    assert calls[-2:] == [("stop", "web", "backend"), ("start", "backend")]


def test_operations_lock_rejects_concurrent_operation_and_releases(tmp_path):
    first = operations.Production.__new__(operations.Production)
    second = operations.Production.__new__(operations.Production)
    first.lock_path = second.lock_path = tmp_path / "operations.lock"
    with first.lock(), pytest.raises(ValueError, match="Another production operation"):
        with second.lock():
            pytest.fail("Concurrent operation acquired the lock")
    with second.lock():
        pass


def test_invalid_backup_checksum_never_starts_restore_container(tmp_path, monkeypatch):
    import json

    (tmp_path / "database.dump").write_bytes(b"corrupted synthetic dump")
    (tmp_path / "manifest.json").write_text(json.dumps({"sha256": {"database.dump": "wrong"}}))

    def unexpected(*args, **kwargs):
        pytest.fail("Docker must not run when the backup checksum fails")

    monkeypatch.setattr(operations, "run", unexpected)
    with pytest.raises(ValueError, match="checksum mismatch"):
        operations.restore_check(tmp_path)
