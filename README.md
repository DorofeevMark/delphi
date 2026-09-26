# Delphi Code local code search

A small Python CLI for agents searching local source trees. It runs one command at a time, with no daemon, server, account, cloud embedding provider, or runtime downloads. This application was implemented independently after inspecting a local reference implementation's behavior and library integration; no reference source, documentation, or branding is included.

## Preparation

The tested target is macOS arm64, with CPython 3.12 supporting SQLite loadable extensions. Some python.org macOS builds disable that feature. `doctor` reports this explicitly. The pinned NumPy and PyTorch wheels used here require macOS 14 or later. CPU inference is used.

After the first PyPI release, install with:

```sh
uv tool install --python 3.12 delphi-code
delphi-code setup
```

Install from this checkout with a Python 3.12 build that supports SQLite extensions:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip install --no-deps --no-build-isolation .
.venv/bin/delphi-code setup
```

With uv already installed, the shorter local installation is:

```sh
uv tool install --python 3.12 /absolute/path/to/delphi-code
delphi-code setup
delphi-code index -p /absolute/path/to/project
delphi-code search 'where are user passwords checked?'
```

The package is not yet published; install from the checkout or a built wheel. The pinned dependency freeze records the tested macOS environment, not a cross-platform lock. Linux has not yet been verified; Windows is not supported by the current file locking implementation.

`setup` explicitly downloads the pinned MiniLM revision in a separate provisioning process. It validates every expected file against bundled SHA-256 hashes, then runs local embedding, SQLite, and native-storage diagnostics before publishing the model directory. Repeated setup verifies and reuses valid assets. Concurrent setup for the same destination fails clearly. Failed downloads or diagnostics leave no published partial model; invalid existing models are preserved with recovery instructions.

For an offline installation, install dependencies from a wheelhouse prepared for the target platform and import the complete prepared MiniLM directory, including its license and model card:

```sh
delphi-code setup --from /absolute/path/to/all-MiniLM-L6-v2
```

`setup --model /absolute/path` selects a different destination; `DELPHI_CODE_MODEL` also overrides it. Setup provisions the pinned MiniLM model only. Custom runtime models remain supported through `--model` or `DELPHI_CODE_MODEL`. Index, search, status, and doctor never download assets.

## Persistent storage and upgrades

Models and indexes are stored outside the installation:

- macOS: `~/Library/Application Support/delphi-code/`
- Linux: `$XDG_DATA_HOME/delphi-code/`, or `~/.local/share/delphi-code/`

The default model is under `models/all-MiniLM-L6-v2/`; indexes are under `indexes/`. `DELPHI_CODE_INDEX_ROOT` overrides the index location. Reinstalling or upgrading the package leaves these directories intact.


## Commands

```sh
.venv/bin/python -m delphi_code doctor --project /path/to/project
.venv/bin/python -m delphi_code index --project /path/to/project
.venv/bin/python -m delphi_code search --project /path/to/project 'where are user passwords checked?'
.venv/bin/python -m delphi_code search --project /path/to/project 'parse configuration' --language python --path 'src/*' --limit 5
.venv/bin/python -m delphi_code status --project /path/to/project
```

An installed package also provides `delphi-code`. `--model /absolute/local/model` overrides `DELPHI_CODE_MODEL`. Without either, Delphi Code uses `models/all-MiniLM-L6-v2` in its user data directory. Missing or incomplete assets fail clearly without downloading anything. This location is independent of the installation directory, working directory, and `--project`. `status` needs no model. Paths are resolved relative to the current working directory; the project root is explicit and is not inferred from Git. After indexing a codebase once, use its folder name with `--project` or `-p`, for example `delphi-code search -p flixbeton "DeliveryNotes"`. A bare name selects a uniquely matching indexed project; duplicate names produce an error listing their paths. Use `./name` or an absolute path to select a directory explicitly. All commands support this lookup, and omitting `--project` searches all stored indexes for `search`; other commands still use the current directory. Cross-project search returns a single globally ranked list, with a full `project` path on each result. `--limit` applies to the combined list, and path/language filters apply within every index. The query is embedded once. All indexes must be readable, complete, and use the selected model; a busy, broken, or incompatible index produces an error rather than silently returning partial results. Use `-p` to restrict the search when needed.

Each command writes one JSON object to stdout, with `schema_version`, `ok`, `command`, and either `data` or `error`. Library progress and diagnostics go to stderr. Argument help uses normal text. Exit codes: 0 success (including no search matches), 2 invalid arguments/project, 3 missing/incompatible model or runtime assets, 4 missing/incomplete/incompatible index, 5 busy index or operational failure. Search results contain project-relative paths, language, inclusive 1-based line ranges, original chunk text, Euclidean distance, and cosine similarity score. Lower distance and higher score mean closer matches; scores are not probabilities. Equal distances use stable path/line/id ordering.

## Offline execution

Before third-party imports, the CLI overrides CocoIndex usage tracking, Hugging Face telemetry, and Hub/Transformers offline environment flags. Models are loaded only from an existing local directory with `local_files_only=True`, `trust_remote_code=False`, and safetensors weights. Supported modules are Transformer, Pooling, Normalize, and Dense. Custom model code, cloud providers, and pickle weights are outside this slice's supported model format. Model files must be trusted and remain unchanged during each command. Full model asset hashes prevent accidentally searching an index with different weights or configuration.

A Python audit guard rejects Internet socket operations and DNS resolution. For an OS boundary that covers native extensions as well, run commands under the target sandbox:

```sh
/usr/bin/sandbox-exec -p '(version 1)(allow default)(deny network*)' \
  .venv/bin/python -m delphi_code index --project /path/to/project
```

The audit guard is defense in depth, not a replacement for OS isolation. In this session, Codex’s own filesystem sandbox denied CocoIndex native storage initialization with `EPERM`; the dedicated macOS profile above successfully ran indexing with all networking denied. `doctor` probes native storage and reports `sandbox_storage_denied` for the stricter environment. Launching that dedicated profile from Codex requires its tool approval; the application does not escalate itself. The CLI uses local filesystem access, threads, SQLite extensions, and CocoIndex's LMDB memory maps. It needs read access to source and model files and write access to Delphi Code's user index directory. No network permission is needed. `doctor` probes CocoIndex storage, then runs an actual local embedding and sqlite-vec distance calculation; it reports the Python guard, not a claim that an external OS sandbox is active.

## Indexing and filters

CocoIndex memoizes each file's content-dependent computation and maintains its exported SQLite vec0 rows. Changed contents are detected even when timestamps are unchanged. Deletions and files newly excluded by rules remove their rows. All candidate files are read on every index command; unchanged files skip chunking and embedding. This intentionally simple version keeps the selected file contents in memory during indexing.

Nested `.gitignore` and `.delphi-codeignore` files apply with Git-style patterns and negation; an ignored parent directory is not traversed. `.delphi-codeignore` follows `.gitignore` within each directory. Repeated `--ignore` patterns add an exclusion layer. Git's global ignore file and `.git/info/exclude` are not read. Built-in exclusions are `.git`, `.delphi-code`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.models`, and the selected model directory. Symlinks, binary/non-UTF-8 data, blank files, and files over `--max-bytes` (default 1 MiB) are skipped. Unknown languages are indexed as `text`.

Repeated `--path` globs are alternatives over project-relative POSIX paths (`*` can match `/`); repeated `--language` values are alternatives using CocoIndex language names such as `python`, `rust`, and `typescript`. Path and language filters combine with AND. On `index`, filters define the entire indexed set for that invocation and excluded old entries are removed. Repeating `index` without flags returns to the default full selection. On `search`, filters restrict results before ranking, so a matching result cannot be lost behind unfiltered top-k candidates.

The code splitter targets 900-byte chunks with overlap. Embeddings are normalized CPU SentenceTransformers outputs with the same model configuration for index and query. Models with asymmetric query/document instructions are not specially configured in this slice. MiniLM is a small general-purpose smoke-test model, not a claim of optimal code retrieval quality. The model's token limit can truncate long chunks.

Search uses sqlite-vec exact distance evaluation over filtered vec0 rows. This is deliberately a full scan, suitable for the initial small-codebase slice; it is not an approximate-nearest-neighbor service.

Each target project has one index in `<user-data>/delphi-code/indexes/<sha256-of-resolved-project-path>/`, independent of the working directory and package installation. `DELPHI_CODE_INDEX_ROOT` can override the central index root. Command output includes `index_directory`, and the manifest records the target project path. Each index contains CocoIndex incremental state, the SQLite vector table, and a manifest. A file lock prevents reading during updates or concurrent writers. An interrupted/failed update leaves `ready: false`; search refuses it until indexing succeeds. This is not an atomic last-good-snapshot design. To use different model assets or rebuild incompatible state, move the specific `index_directory` aside and run `index` again. Moving a target project changes its index identity. `status` reports stored state and does not rescan source files to detect staleness.

## Verification and provenance

Run the 23 regular tests from the checkout root:

```sh
bash scripts/test.sh
```

These cover setup logic, project resolution, storage paths, model defaults, and cross-project ranking with real SQLite and mocked embeddings. They need installed dependencies, but no prepared model or OS network sandbox. They make no external requests; importing Delphi Code still installs its normal Python network guard. Plain `.venv/bin/python -m unittest discover -s tests -v` runs this same suite.

Run the 3 offline integration tests separately on macOS with a prepared model:

```sh
export DELPHI_CODE_TEST_MODEL="$HOME/Library/Application Support/delphi-code/models/all-MiniLM-L6-v2"
bash scripts/test_offline.sh
```

Set `DELPHI_CODE_TEST_MODEL` to the actual model location; a model prepared inside this checkout can instead use `export DELPHI_CODE_TEST_MODEL="$PWD/.models/all-MiniLM-L6-v2"`. Both scripts accept `DELPHI_CODE_PYTHON` to select a different Python executable.

The separate `tests/offline` suite launches real CLI subprocesses under OS network denial, uses an empty Hugging Face cache, and records Python DNS/connect attempts before runtime imports. It covers offline model import/reuse, missing models, doctor, actual retrieval, same-content reuse, preserved-mtime edits, deletion, ignore negation, filters, line numbers, empty results, and JSON/exit codes. A separate socket probe verifies the OS blocks networking. This directory is intentionally outside regular unittest discovery. Run both commands for the full 26-test check; neither suite tests live model downloads.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for dependency/model provenance and redistribution notes. The application package does not bundle dependencies or model weights. For a bundled release, run `scripts/collect_notices.py` in the release environment and `scripts/prepare_notices.py` during online preparation to collect notices under `build/third_party/`; review and include them with that release. The model asset hashes are retained in `MODEL_PROVENANCE.json`.

## Publishing

The `Publish` GitHub Actions workflow builds and validates distributions on pushes to `main`. Version tags such as `v0.1.0` also publish after the macOS installation, online setup, and offline tests pass. The tag must match the version in `pyproject.toml`.

Before the first release, configure a pending Trusted Publisher in your PyPI account: project `delphi-code`, owner `DorofeevMark`, repository `delphi-code`, workflow `publish.yml`, environment `pypi`. Then push the matching version tag. Publishing uses GitHub OIDC; no stored PyPI token is required.
