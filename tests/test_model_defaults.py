import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from delphi.cli import arguments


class ModelDefaults(unittest.TestCase):
    def test_override_precedence(self):
        with patch.dict(os.environ, {"DELPHI_MODEL": "/configured/model"}):
            with patch.object(sys, "argv", ["delphi", "index"]):
                self.assertEqual(arguments().model, "/configured/model")
            with patch.object(sys, "argv", ["delphi", "index", "--model", "/explicit/model"]):
                self.assertEqual(arguments().model, "/explicit/model")

    def test_cli_uses_default_without_environment(self):
        with patch.dict(os.environ, {}, clear=True), patch("delphi.cli.model_directory", return_value=Path("/local/default")), patch.object(sys, "argv", ["delphi", "search", "query"]):
            self.assertEqual(arguments().model, Path("/local/default"))
