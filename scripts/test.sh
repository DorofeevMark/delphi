set -eu
: "${DELPHI_PYTHON:=.venv/bin/python}"
exec "$DELPHI_PYTHON" -m unittest discover -s tests -v
