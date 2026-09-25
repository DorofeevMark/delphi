import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from delphi.cli import index_directory, locked


class IndexDirectory(unittest.TestCase):
    def test_default_is_inside_delphi(self):
        with patch.dict(os.environ, {}, clear=True):
            state = index_directory(Path('/tmp/example'))
        self.assertEqual(state.parent, Path(__file__).resolve().parents[1] / '.delphi/indexes')

    def test_projects_with_same_name_are_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with patch.dict(os.environ, {'DELPHI_INDEX_ROOT': str(root / 'indexes')}):
                first = index_directory(root / 'one/project')
                second = index_directory(root / 'two/project')
                self.assertNotEqual(first, second)
                self.assertEqual(first, index_directory(root / 'one/other/../project'))
                with locked(first, True):
                    self.assertTrue((first / 'lock').is_file())
                self.assertFalse(second.exists())

    def test_symlink_uses_same_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / 'project'
            project.mkdir()
            alias = root / 'alias'
            alias.symlink_to(project)
            self.assertEqual(index_directory(project), index_directory(alias))
