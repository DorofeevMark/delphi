# Delphi local code search

A small Python CLI for agents searching local source trees. It runs one command at a time, with no daemon, server, account, cloud embedding provider, or runtime downloads. This application was implemented independently after inspecting a local reference implementation's behavior and library integration; no reference source, documentation, or branding is included.

## Preparation

The tested target is macOS arm64, with CPython 3.12 supporting SQLite loadable extensions. Some python.org macOS builds disable that feature. `doctor` reports this explicitly. The pinned NumPy and PyTorch wheels used here require macOS 14 or later. CPU inference is used.

Prepare dependencies and model assets on a network-enabled machine before entering the sandbox:

```sh
python3 -m venv venv
venv/bin/python -m pip install -r requirements-lock.txt
venv/bin/python -m pip install --no-deps --no-build-isolation .
venv/bin/python scripts/prepare_model.py .models/all-MiniLM-L6-v2
```

Use a Python build with extension loading enabled for the first command (a uv-managed Python is one option). `requirements-lock.txt` records the tested environment's exact versions; it is a version freeze, not a wheel hash lock or cross-platform lock. For an air-gapped deployment, prepare a wheelhouse for the target Python/OS and install it with `pip --no-index --find-links=/path/to/wheelhouse`. Distribute the complete model directory separately, including its license, model card, and provenance manifest. Model preparation and supplemental release-notice preparation use the network; neither is imported by the runtime.

## Commands

```sh
venv/bin/python -m delphi doctor --project /path/to/project
venv/bin/python -m delphi index --project /path/to/project
venv/bin/python -m delphi search --project /path/to/project 'where are user passwords checked?'
venv/bin/python -m delphi search --project /path/to/project 'parse configuration' --language python --path 'src/*' --limit 5
venv/bin/python -m delphi status --project /path/to/project
```

An installed package also provides `delphi`. `--model /absolute/local/model` overrides `DELPHI_MODEL`. Without either, Delphi looks for `.models/all-MiniLM-L6-v2` beside the source package, then beside the virtual environment, then `~/.local/share/delphi/models/all-MiniLM-L6-v2`. The first existing directory is used and validated; incomplete assets fail clearly without downloading anything. Discovery is independent of the working directory and `--project`. The prepared model in this checkout is found automatically. `status` needs no model. Paths are resolved relative to the current working directory; the project root is explicit and is not inferred from Git.

Each command writes one JSON object to stdout, with `schema_version`, `ok`, `command`, and either `data` or `error`. Library progress and diagnostics go to stderr. Argument help uses normal text. Exit codes: 0 success (including no search matches), 2 invalid arguments/project, 3 missing/incompatible model or runtime assets, 4 missing/incomplete/incompatible index, 5 busy index or operational failure. Search results contain project-relative paths, language, inclusive 1-based line ranges, original chunk text, Euclidean distance, and cosine similarity score. Lower distance and higher score mean closer matches; scores are not probabilities. Equal distances use stable path/line/id ordering.

## Offline execution

Before third-party imports, the CLI overrides CocoIndex usage tracking, Hugging Face telemetry, and Hub/Transformers offline environment flags. Models are loaded only from an existing local directory with `local_files_only=True`, `trust_remote_code=False`, and safetensors weights. Supported modules are Transformer, Pooling, Normalize, and Dense. Custom model code, cloud providers, and pickle weights are outside this slice's supported model format. Model files must be trusted and remain unchanged during each command. Full model asset hashes prevent accidentally searching an index with different weights or configuration.

A Python audit guard rejects Internet socket operations and DNS resolution. For an OS boundary that covers native extensions as well, run commands under the target sandbox:

```sh
/usr/bin/sandbox-exec -p '(version 1)(allow default)(deny network*)' \
  venv/bin/python -m delphi index --project /path/to/project
```

The audit guard is defense in depth, not a replacement for OS isolation. In this session, Codex’s own filesystem sandbox denied CocoIndex native storage initialization with `EPERM`; the dedicated macOS profile above successfully ran indexing with all networking denied. `doctor` probes native storage and reports `sandbox_storage_denied` for the stricter environment. Launching that dedicated profile from Codex requires its tool approval; the application does not escalate itself. The CLI uses local filesystem access, threads, SQLite extensions, and CocoIndex's LMDB memory maps. It needs read access to source and model files and write access to Delphi's central `.delphi/indexes` directory. No network permission is needed. `doctor` probes CocoIndex storage, then runs an actual local embedding and sqlite-vec distance calculation; it reports the Python guard, not a claim that an external OS sandbox is active.

## Indexing and filters

CocoIndex memoizes each file's content-dependent computation and maintains its exported SQLite vec0 rows. Changed contents are detected even when timestamps are unchanged. Deletions and files newly excluded by rules remove their rows. All candidate files are read on every index command; unchanged files skip chunking and embedding. This intentionally simple version keeps the selected file contents in memory during indexing.

Nested `.gitignore` and `.delphiignore` files apply with Git-style patterns and negation; an ignored parent directory is not traversed. `.delphiignore` follows `.gitignore` within each directory. Repeated `--ignore` patterns add an exclusion layer. Git's global ignore file and `.git/info/exclude` are not read. Built-in exclusions are `.git`, `.delphi`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.models`, and the selected model directory. Symlinks, binary/non-UTF-8 data, blank files, and files over `--max-bytes` (default 1 MiB) are skipped. Unknown languages are indexed as `text`.

Repeated `--path` globs are alternatives over project-relative POSIX paths (`*` can match `/`); repeated `--language` values are alternatives using CocoIndex language names such as `python`, `rust`, and `typescript`. Path and language filters combine with AND. On `index`, filters define the entire indexed set for that invocation and excluded old entries are removed. Repeating `index` without flags returns to the default full selection. On `search`, filters restrict results before ranking, so a matching result cannot be lost behind unfiltered top-k candidates.

The code splitter targets 900-byte chunks with overlap. Embeddings are normalized CPU SentenceTransformers outputs with the same model configuration for index and query. Models with asymmetric query/document instructions are not specially configured in this slice. MiniLM is a small general-purpose smoke-test model, not a claim of optimal code retrieval quality. The model's token limit can truncate long chunks.

Search uses sqlite-vec exact distance evaluation over filtered vec0 rows. This is deliberately a full scan, suitable for the initial small-codebase slice; it is not an approximate-nearest-neighbor service.

Each target project has one index in `<delphi>/.delphi/indexes/<sha256-of-resolved-project-path>/`, independent of the working directory. In a source checkout, `<delphi>` is the repository root; with the documented virtual-environment installation it is the directory containing the environment. `DELPHI_INDEX_ROOT` can override the central index root. Command output includes `index_directory`, and the manifest records the target project path. Each index contains CocoIndex incremental state, the SQLite vector table, and a manifest. A file lock prevents reading during updates or concurrent writers. An interrupted/failed update leaves `ready: false`; search refuses it until indexing succeeds. This is not an atomic last-good-snapshot design. To use different model assets or rebuild incompatible state, move the specific `index_directory` aside and run `index` again. Old per-project `.delphi` indexes are not read or migrated; run `index` once to rebuild them centrally. Moving a target project changes its index identity. `status` reports stored state and does not rescan source files to detect staleness.

## Verification and provenance

```sh
export DELPHI_TEST_MODEL="$PWD/.models/all-MiniLM-L6-v2"
bash scripts/test_offline.sh
```

The suite launches real CLI subprocesses under OS network denial, uses an empty Hugging Face cache, and records Python DNS/connect attempts before runtime imports. It covers missing models, doctor, actual retrieval, same-content reuse, preserved-mtime edits, deletion, ignore negation, filters, line numbers, empty results, and JSON/exit codes. A separate socket probe verifies the OS blocks networking.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for dependency/model provenance and redistribution notes. The application package does not bundle dependencies or model weights. For a bundled release, run `scripts/collect_notices.py` in the release environment and `scripts/prepare_notices.py` during online preparation to collect notices under `build/third_party/`; review and include them with that release. The model asset hashes are retained in `MODEL_PROVENANCE.json`.
