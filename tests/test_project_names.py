import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from delphi_code.cli import index_directory, resolve_project
from delphi_code.model import Failure


class ProjectNames(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.environment = patch.dict(os.environ, {"DELPHI_CODE_INDEX_ROOT": str(self.root / "indexes")})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def register(self, relative):
        project = self.root / relative
        project.mkdir(parents=True)
        state = index_directory(project)
        state.mkdir(parents=True)
        (state / "manifest.json").write_text(json.dumps({"project": str(project)}))
        return project

    def test_unique_name(self):
        project = self.register("one/flixbeton")
        self.assertEqual(resolve_project("flixbeton"), project)

    def test_duplicate_names_require_path(self):
        first = self.register("one/flixbeton")
        second = self.register("two/flixbeton")
        with self.assertRaises(Failure) as raised:
            resolve_project("flixbeton")
        self.assertEqual(raised.exception.code, "project_ambiguous")
        self.assertIn(str(first), str(raised.exception))
        self.assertIn(str(second), str(raised.exception))
        self.assertEqual(resolve_project(str(first)), first)
        self.assertEqual(resolve_project("./flixbeton"), Path("flixbeton").resolve())

    def test_unindexed_paths_still_work(self):
        self.assertEqual(resolve_project("unindexed"), Path("unindexed").resolve())
        self.assertEqual(resolve_project("."), Path.cwd())

    def test_invalid_manifests_do_not_break_lookup(self):
        project = self.register("one/flixbeton")
        invalid = self.root / "indexes/invalid"
        invalid.mkdir()
        for content in ("{", "null", '{"project": 42}', '{"project": "/incorrect/flixbeton"}'):
            (invalid / "manifest.json").write_text(content)
            self.assertEqual(resolve_project("flixbeton"), project)
