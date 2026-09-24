import argparse
import asyncio
from contextlib import contextmanager, redirect_stdout
import fcntl
from importlib.metadata import version
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone

from .model import Failure, embed, inspect_model, load_model


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Failure("usage", message, 2)


def arguments():
    parser = Parser(prog="delphi", description="Offline local code search")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("index", "search", "status", "doctor"):
        command = commands.add_parser(name)
        command.add_argument("--project", type=Path, default=Path.cwd())
        if name != "status":
            command.add_argument("--model", default=os.environ.get("DELPHI_MODEL"))
        if name in {"index", "search"}:
            command.add_argument("--path", action="append", default=[], help="Project-relative glob; repeat for alternatives")
            command.add_argument("--language", action="append", default=[])
        if name == "index":
            command.add_argument("--ignore", action="append", default=[])
            command.add_argument("--max-bytes", type=int, default=1_048_576)
        if name == "search":
            command.add_argument("query")
            command.add_argument("--limit", type=int, default=10)
    return parser.parse_args()


@contextmanager
def database(path):
    import sqlite_vec

    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        db.row_factory = sqlite3.Row
        yield db
    finally:
        db.close()


@contextmanager
def locked(state, exclusive):
    if exclusive:
        state.mkdir(exist_ok=True)
    if not state.is_dir():
        raise Failure("index_missing", "No index exists; run index first", 4)
    try:
        with (state / "lock").open("a" if exclusive else "r") as lock:
            try:
                fcntl.flock(lock, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Failure("index_busy", "Another command is updating this project", 5) from exc
            yield
    except FileNotFoundError as exc:
        raise Failure("index_missing", "No index exists; run index first", 4) from exc


def metadata(state):
    if not (state / "manifest.json").is_file():
        raise Failure("index_missing", "No completed index exists; run index first", 4)
    result = json.loads((state / "manifest.json").read_text())
    if result.get("schema_version") != 1:
        raise Failure("index_incompatible", "Unsupported index version", 4)
    return result


def write_metadata(state, data):
    temporary = state / "manifest.tmp"
    temporary.write_text(json.dumps(data, sort_keys=True) + "\n")
    temporary.replace(state / "manifest.json")


def counts(state):
    with database(state / "vectors.sqlite") as db:
        row = db.execute("SELECT count(*) AS chunks, count(DISTINCT path) AS files FROM passages").fetchone()
        return dict(row)


def execute(args):
    project = args.project.expanduser().resolve()
    if not project.is_dir():
        raise Failure("project_missing", f"Project directory does not exist: {project}", 2)
    state = project / ".delphi"
    if args.command == "status":
        with locked(state, False):
            info = metadata(state)
            return {"project": str(project), **info, **(counts(state) if info["ready"] else {})}
    if args.command == "search" and (not args.query.strip() or not 1 <= args.limit <= 1000):
        raise Failure("usage", "Query must be nonempty and --limit must be between 1 and 1000", 2)
    if args.command == "index" and args.max_bytes < 1:
        raise Failure("usage", "--max-bytes must be positive", 2)
    model_path, identity = inspect_model(args.model)
    if not hasattr(sqlite3.Connection, "enable_load_extension"):
        raise Failure("sqlite_extensions_unavailable", "This Python disables SQLite extension loading; provision a Python build with loadable SQLite extensions", 3)
    if args.command == "doctor":
        import cocoindex
        import sqlite_vec

        from .indexing import check_storage

        with tempfile.TemporaryDirectory(prefix="delphi-doctor-") as scratch:
            asyncio.run(check_storage(Path(scratch)))
        model = load_model(model_path)
        vector = embed(model, ["local code search"])[0]
        db = sqlite3.connect(":memory:")
        try:
            db.enable_load_extension(True)
            sqlite_vec.load(db)
            db.enable_load_extension(False)
            distance = db.execute("SELECT vec_distance_L2(?, ?)", (vector.tobytes(), vector.tobytes())).fetchone()[0]
        finally:
            db.close()
        return {
            "project": str(project), "model": str(model_path), "model_sha256": identity,
            "dimensions": len(vector), "self_distance": distance, "device": "cpu",
            "cocoindex_storage": "ok", "offline": True, "network_guard": "python_audit", "sqlite": sqlite3.sqlite_version,
            "dependencies": {name: version(name) for name in ("cocoindex", "sqlite-vec", "sentence-transformers", "torch")},
        }
    with locked(state, args.command == "index"):
        previous = metadata(state) if (state / "manifest.json").exists() else None
        if previous and previous["model_sha256"] != identity:
            raise Failure("model_mismatch", "Model assets differ from the index; restore the original model or move .delphi aside and reindex", 4)
        if args.command == "index":
            from .files import collect
            from .indexing import run

            model = load_model(model_path)
            sources, skipped = collect(project, args.path, args.language, args.ignore, model_path, args.max_bytes)
            info = {
                "schema_version": 1, "ready": False, "model": str(model_path), "model_sha256": identity,
                "paths": args.path, "languages": args.language, "ignores": args.ignore,
                "max_bytes": args.max_bytes,
            }
            write_metadata(state, info)
            stats = asyncio.run(run(state, sources, model, identity))
            info.update(ready=True, indexed_at=datetime.now(timezone.utc).isoformat())
            total = counts(state)
            write_metadata(state, info)
            return {"project": str(project), **total, "skipped": skipped, "incremental": stats}
        if previous is None:
            raise Failure("index_missing", "Run index first", 4)
        if not previous["ready"]:
            raise Failure("index_incomplete", "Last index did not complete; run index again before searching", 4)
        model = load_model(model_path)
        vector = embed(model, [args.query])[0].tobytes()
        conditions, parameters = [], [vector]
        if args.language:
            conditions.append("language IN (" + ",".join("?" for _ in args.language) + ")")
            parameters.extend(args.language)
        if args.path:
            conditions.append("(" + " OR ".join("path_matches(path, ?)" for _ in args.path) + ")")
            parameters.extend(args.path)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        with database(state / "vectors.sqlite") as db:
            import fnmatch

            db.create_function("path_matches", 2, fnmatch.fnmatchcase, deterministic=True)
            rows = db.execute(
                "SELECT path, language, text, start_line, end_line, vec_distance_L2(vector, ?) AS distance "
                "FROM passages" + where + " ORDER BY distance, path, start_line, id LIMIT ?",
                [*parameters, args.limit],
            ).fetchall()
        return {"project": str(project), "query": args.query, "results": [
            {**dict(row), "score": max(-1.0, min(1.0, 1.0 - row["distance"] ** 2 / 2.0))} for row in rows
        ]}


def main():
    command = None
    exit_code = 0
    try:
        args = arguments()
        command = args.command
        with redirect_stdout(sys.stderr):
            result = execute(args)
        payload = {"schema_version": 1, "ok": True, "command": command, "data": result}
    except Exception as exc:
        if os.environ.get("DELPHI_DEBUG") == "1":
            import traceback

            traceback.print_exc(file=sys.stderr)
        failure = exc if isinstance(exc, Failure) else Failure(
            "dependency_missing" if isinstance(exc, ModuleNotFoundError) else "runtime_error",
            str(exc), 3 if isinstance(exc, ModuleNotFoundError) else 5,
        )
        exit_code = failure.exit_code
        print(f"delphi: {failure}", file=sys.stderr)
        payload = {"schema_version": 1, "ok": False, "command": command,
                   "error": {"code": failure.code, "message": str(failure)}}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False))
    raise SystemExit(exit_code)
