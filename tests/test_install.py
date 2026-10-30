import json
from pathlib import Path
import sys
import tempfile
import unittest

import hook_config
import manage

ROOT = Path(__file__).resolve().parents[1]


class HookTests(unittest.TestCase):
    def setUp(self):
        self.app = Path('C:/Example User/Alerts/alerts.py')
        self.python = Path('C:/Example User/Python/python.exe')

    def test_idempotent_and_preserves_unrelated_hooks(self):
        other = {'type':'command','command':'echo another','statusMessage':'other'}
        initial = {'description':'Keep me','hooks':{'Stop':[{'matcher':'custom','hooks':[other]}],
                                                   'SessionStart':[{'hooks':[other]}]}}
        once = hook_config.install(initial,self.python,self.app)
        twice = hook_config.install(once,self.python,self.app)
        self.assertEqual(once, twice)
        self.assertEqual(hook_config.remove(twice,self.app), initial)

    def test_mixed_group_keeps_other_handler_and_metadata(self):
        config = hook_config.install({},self.python,self.app)
        other = {'type':'command','command':'echo keep'}
        config['hooks']['Stop'][0].update({'matcher':'custom','extra':'metadata'})
        config['hooks']['Stop'][0]['hooks'].append(other)
        result = hook_config.remove(config,self.app)
        self.assertEqual(result['hooks']['Stop'], [{'matcher':'custom','extra':'metadata','hooks':[other]}])

    def test_marker_alone_is_not_ownership(self):
        other = {'type':'command','statusMessage':hook_config.MARKER,'command':'"C:/other/alerts.py" --hook'}
        initial = {'hooks':{'Stop':[{'hooks':[other]}]}}
        self.assertEqual(hook_config.remove(initial,self.app), initial)

    def test_shell_metacharacters_refused(self):
        for path in ('C:/bad&name/alerts.py','C:/bad%VAR%/alerts.py','C:/bad"/alerts.py'):
            with self.assertRaises(ValueError):
                hook_config.command_for(self.python,path)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.target = self.root / 'App With Spaces'
        self.codex = self.root / 'Codex With Spaces'
        self.codex.mkdir()
        self.before = {'description':'user config','hooks':{'Stop':[{'hooks':[{'type':'command','command':'echo other'}]}]}}
        manage.atomic_json(self.codex / 'hooks.json', self.before)

    def tearDown(self):
        self.temp.cleanup()

    def install(self, preview=False):
        return manage.install_files(ROOT,self.target,self.codex,Path(sys.executable),preview=preview)

    def test_preview_has_no_writes(self):
        before = (self.codex / 'hooks.json').read_bytes()
        self.install(preview=True)
        self.assertFalse(self.target.exists())
        self.assertEqual((self.codex / 'hooks.json').read_bytes(), before)

    def test_install_twice_and_uninstall_preserve_config(self):
        self.install()
        first = manage.read_json(self.codex / 'hooks.json')
        self.install()
        self.assertEqual(manage.read_json(self.codex / 'hooks.json'), first)
        self.assertTrue((self.target / 'manifest.json').exists())
        self.assertTrue(list((self.target / 'backups').glob('*.json')))
        manage.uninstall(self.target)
        self.assertEqual(manage.read_json(self.codex / 'hooks.json'), self.before)
        self.assertTrue((self.target / 'disabled').exists())
        self.assertTrue((self.target / 'alerts.py').exists())

    def test_invalid_existing_json_is_never_overwritten(self):
        path = self.codex / 'hooks.json'
        path.write_text('{invalid')
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(path.read_text(), '{invalid')
        self.assertFalse(self.target.exists())

    def test_disabled_hooks_require_user_decision(self):
        (self.codex / 'config.toml').write_text('[features]\nhooks=false\n')
        with self.assertRaises(ValueError):
            self.install()
        self.assertFalse(self.target.exists())

    def test_custom_codex_home_cannot_be_silently_changed(self):
        self.install()
        with self.assertRaises(ValueError):
            manage.install_files(ROOT,self.target,self.root/'other',Path(sys.executable))


if __name__ == '__main__':
    unittest.main()
