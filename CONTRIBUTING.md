# Contributing

## Development setup

Use a Python 3.12 build that supports SQLite loadable extensions, such as a uv-managed one:

```sh
uv venv --python 3.12 --managed-python .venv
uv pip install -r requirements-lock.txt
uv pip install --no-deps --no-build-isolation -e .
.venv/bin/delphi-code setup
```

## Tests

Run the regular suite from the checkout root:

```sh
bash scripts/test.sh
```

It covers setup logic, project resolution, storage paths, model defaults, and cross-project ranking with real SQLite and mocked embeddings. It needs installed dependencies, but no prepared model or OS network sandbox, and makes no external requests; importing Delphi Code still installs its normal Python network guard. `.venv/bin/python -m unittest discover -s tests -v` runs the same suite.

Run the offline integration suite separately, on macOS with a prepared model:

```sh
export DELPHI_CODE_TEST_MODEL="$HOME/Library/Application Support/delphi-code/models/all-MiniLM-L6-v2"
bash scripts/test_offline.sh
```

Set `DELPHI_CODE_TEST_MODEL` to the actual model location; a model prepared inside the checkout can use `"$PWD/.models/all-MiniLM-L6-v2"`. Both scripts accept `DELPHI_CODE_PYTHON` to select a different Python executable.

The `tests/offline` suite launches real CLI subprocesses under OS network denial, uses an empty Hugging Face cache, and records Python DNS/connect attempts before runtime imports. It covers offline model import and reuse, missing models, doctor, actual retrieval, same-content reuse, preserved-mtime edits, deletion, ignore negation, filters, line numbers, empty results, and JSON output and exit codes. A separate socket probe verifies that the OS blocks networking. The directory is intentionally outside regular unittest discovery, so run both scripts for the full check. Neither suite tests live model downloads; CI does (see below).

## Third-party notices

For a release that bundles dependencies, run `scripts/collect_notices.py` in the release environment and `scripts/prepare_notices.py` during online preparation. Both collect notices under `build/third_party/`; review them and include them with that release. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Releasing

The `Publish` GitHub Actions workflow builds and validates distributions on every push to `main`, then installs the wheel on macOS, runs an online `delphi-code setup`, both test suites, and a smoke test outside the checkout.

To release:

1. Bump `version` in `pyproject.toml` and push to `main`.
2. Once the workflow passes, push a matching tag, for example `git tag v0.1.1 && git push origin v0.1.1`. The tag must match the package version.

The tag run repeats the checks and publishes to PyPI through a Trusted Publisher (project `delphi-code`, owner `DorofeevMark`, repository `delphi-code`, workflow `publish.yml`, environment `pypi`). Publishing uses GitHub OIDC; no stored PyPI token is needed. PyPI never accepts the same version twice.
