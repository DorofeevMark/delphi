set -eu
: "${DELPHI_CODE_PYTHON:=.venv/bin/python}"
exec "$DELPHI_CODE_PYTHON" -m unittest discover -s tests -v
