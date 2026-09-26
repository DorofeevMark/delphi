set -eu
: "${DELPHI_TEST_MODEL:?Set DELPHI_TEST_MODEL to an absolute model directory}"
: "${DELPHI_PYTHON:=.venv/bin/python}"
export DELPHI_OS_SANDBOX=1
exec /usr/bin/sandbox-exec -p '(version 1)(allow default)(deny network*)' "$DELPHI_PYTHON" -m unittest discover -s tests/offline -v
