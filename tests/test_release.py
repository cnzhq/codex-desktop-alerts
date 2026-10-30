import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_release', ROOT / 'scripts/build_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_deterministic_allowlisted_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            archive, first = release.build(output=Path(folder))
            _, second = release.build(output=Path(folder))
            self.assertEqual(first, second)
            with zipfile.ZipFile(archive) as bundle:
                names = bundle.namelist()
                self.assertTrue(any(name.endswith('/README.md') for name in names))
                self.assertTrue(any(name.endswith('/LICENSE') for name in names))
                for name in names:
                    self.assertNotIn('__pycache__', name)
                    self.assertNotIn('/.git/', name)
                    self.assertNotIn('/backups/', name)
                    self.assertNotIn('/queue/', name)
                    self.assertFalse(name.endswith(('auth.json','history.jsonl','manifest.json')))


if __name__ == '__main__':
    unittest.main()
