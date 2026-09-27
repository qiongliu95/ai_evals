"""Append-only raw journal, immutable task snapshot, and OS-released run lock."""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
from uuid import uuid4

from .result_schema import Task


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    if not Path(path).exists():
        return []
    rows = []
    with Path(path).open(encoding="utf-8") as stream:
        for index, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                # Never silently discard damaged evidence or replay billed requests.
                raise ValueError(f"Invalid JSONL: {path}, line {index}; preserve and inspect the file") from exc
    return rows


def write_json(path, value):
    path = Path(path)
    # 以原子方式替换已写完的临时文件，避免读取方看到不完整的 JSON。
    tmp = path.with_name(path.name + ".tmp-" + uuid4().hex)
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_jsonl(path, rows):
    path = Path(path)
    # 派生 JSONL 也使用相同的全有或全无替换保证。
    tmp = path.with_name(path.name + ".tmp-" + uuid4().hex)
    with tmp.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def effective_results(rows):
    """First success wins; otherwise use the latest failed attempt."""
    result = {}
    for row in rows:
        key = row["sample_id"]
        if result.get(key, {}).get("status") != "success":
            result[key] = row
    return list(result.values())


class RunManager:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.config = json.loads((self.path / "config.json").read_text(encoding="utf-8"))
        if digest(self.path / "tasks.jsonl") != self.config["tasks_sha256"]:
            raise ValueError("Task snapshot changed; refusing to resume a different experiment")

    @classmethod
    def create(cls, root, config, tasks):
        ids = [task.sample_id for task in tasks]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("Tasks must be nonempty with unique sample_id values")
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:12]
        path = Path(root) / run_id
        path.mkdir(parents=True, exist_ok=False)
        write_jsonl(path / "tasks.jsonl", [asdict(task) for task in tasks])
        saved = dict(config, run_id=run_id, created_at=now(), schema_version=1,
                     tasks_sha256=digest(path / "tasks.jsonl"), sample_count=len(tasks),
                     runtime={"python": sys.version, "platform": platform.platform(), "workspace_version": "0.1.0"})
        write_json(path / "config.json", saved)
        (path / "raw.jsonl").touch(exist_ok=False)
        return cls(path)

    def tasks(self):
        return [Task(**row) for row in read_jsonl(self.path / "tasks.jsonl")]

    def raw(self):
        rows = read_jsonl(self.path / "raw.jsonl")
        for row in rows:
            if row["run_config"] != self.config:
                raise ValueError("Raw result and saved configuration differ")
        return rows

    def append(self, result):
        # One durable record per completed attempt; raw.jsonl is never rewritten.
        payload = (json.dumps(asdict(result), ensure_ascii=False) + "\n").encode("utf-8")
        with (self.path / "raw.jsonl").open("ab") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())

    @contextmanager
    def lock(self):
        # OS locks release on process death, so a stale lock file is harmless.
        with (self.path / ".run.lock").open("a+b") as stream:
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                acquire = lambda: msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                release = lambda: msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                acquire = lambda: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                release = lambda: fcntl.flock(stream, fcntl.LOCK_UN)
            try:
                acquire()
            except OSError as exc:
                raise RuntimeError("This run is already in use") from exc
            try:
                yield
            finally:
                stream.seek(0)
                release()
