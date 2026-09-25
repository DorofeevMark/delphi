import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from delphi.cli import arguments
from delphi.model import Failure, default_model, inspect_model


class ModelDefaults(unittest.TestCase):
    def test_override_precedence(self):
        with patch.dict(os.environ, {"DELPHI_MODEL": "/configured/model"}):
            with patch.object(sys, "argv", ["delphi", "index"]):
                self.assertEqual(arguments().model, "/configured/model")
            with patch.object(sys, "argv", ["delphi", "index", "--model", "/explicit/model"]):
                self.assertEqual(arguments().model, "/explicit/model")

    def test_discovery_from_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "source/delphi/model.py"
1            prefix = root / "installed/.venv"
            user_model = root / "home/.local/share/delphi/models/all-MiniLM-L6-v2"
            with patch("delphi.model.__file__", str(source)), patch.object(sys, "prefix", str(prefix)), patch("delphi.model.Path.home", return_value=root / "home"):
                self.assertEqual(default_model(), user_model)
                with self.assertRaises(Failure) as raised:
                    inspect_model(default_model())
                self.assertEqual(raised.exception.code, "model_missing")
                user_model.mkdir(parents=True)
                self.assertEqual(default_model(), user_model)
                installed_model = prefix.parent / ".models/all-MiniLM-L6-v2"
                installed_model.mkdir(parents=True)
                self.assertEqual(default_model(), installed_model)
                source_model = source.parent.parent / ".models/all-MiniLM-L6-v2"
                source_model.mkdir(parents=True)
                self.assertEqual(default_model(), source_model)

    def test_cli_uses_default_without_environment(self):
        with patch.dict(os.environ, {}, clear=True), patch("delphi.cli.default_model", return_value=Path("/local/default")), patch.object(sys, "argv", ["delphi", "search", "query"]):
            self.assertEqual(arguments().model, Path("/local/default"))
