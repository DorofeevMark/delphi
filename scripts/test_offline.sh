set -eu
: "${DELPHI_CODE_TEST_MODEL:?Set DELPHI_CODE_TEST_MODEL to an absolute model directory}"
: "${DELPHI_CODE_PYTHON:=.venv/bin/python}"
export DELPHI_CODE_OS_SANDBOX=1
exec /usr/bin/sandbox-exec -p '(version 1)(allow default)(deny network*)' "$DELPHI_CODE_PYTHON" -m unittest discover -s tests/offline -v
