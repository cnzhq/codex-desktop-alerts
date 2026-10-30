"""Portable file installation and hook management; no model calls or credentials."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import sys
import time
import tomllib
import uuid

import hook_config

APP_FILES = ('alerts.py', 'hook_config.py', 'manage.py', 'uninstall.ps1',
             'README.md', 'NOTICE.md', 'CHANGELOG.md', 'LICENSE')


def read_json(path, default=None):
    if not path.exists():
        return {} if default is None else default
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError(f'Expected a JSON object: {path.name}')
    return value


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def check_config(codex_home):
    config_path = codex_home / 'config.toml'
    if not config_path.exists():
        return []
    config = tomllib.loads(config_path.read_text(encoding='utf-8-sig'))
    if config.get('features', {}).get('hooks') is False:
        raise ValueError('features.hooks=false: enable hooks yourself before installation')
    if config.get('allow_managed_hooks_only') is True:
        raise ValueError('allow_managed_hooks_only=true: user hooks cannot run')
    return ['Inline hooks also exist; inspect the combined list in /hooks.'] if config.get('hooks') else []


def stop_runtime(install_dir, disable=False):
    if not install_dir.exists():
        return
    (install_dir / ('disabled' if disable else 'paused')).touch()
    (install_dir / 'stop.request').touch()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        status = read_json(install_dir / 'status.json')
        if time.time() - status.get('heartbeat', 0) > 12:
            return
        time.sleep(0.25)
    raise RuntimeError('Existing notifier did not stop; installation was not replaced')


def backup_hooks(hook_file, install_dir):
    if hook_file.exists():
        folder = install_dir / 'backups'
        folder.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        shutil.copy2(hook_file, folder / (stamp + '-hooks.json'))


def install_files(source, install_dir, codex_home, python_exe, preview=False):
    source, install_dir, codex_home = (path.resolve() for path in (source, install_dir, codex_home))
    if source == install_dir or source in install_dir.parents or install_dir in source.parents:
        raise ValueError('Install directory and source tree must be separate')
    for filename in APP_FILES:
        if not (source / filename).is_file():
            raise ValueError(f'Missing source file: {filename}')
    warnings = check_config(codex_home)
    hook_file = codex_home / 'hooks.json'
    before = read_json(hook_file)
    after = hook_config.install(before, python_exe, install_dir / 'alerts.py')
    plan = {'install_dir': str(install_dir), 'codex_home': str(codex_home),
            'python_exe': str(python_exe), 'hook_file': str(hook_file),
            'events': list(hook_config.EVENTS), 'requires_hook_review': True,
            'warnings': warnings}
    if preview:
        return plan
    previous_manifest = read_json(install_dir / 'manifest.json')
    if previous_manifest and previous_manifest.get('codex_home') != str(codex_home):
        raise ValueError('Uninstall the existing environment before changing CodexHome')
    stop_runtime(install_dir)
    install_dir.mkdir(parents=True, exist_ok=True)
    for filename in APP_FILES:
        shutil.copy2(source / filename, install_dir / filename)
    docs_target = install_dir / 'docs'
    docs_target.mkdir(exist_ok=True)
    for doc in (source / 'docs').glob('*.md'):
        shutil.copy2(doc, docs_target / doc.name)
    backup_hooks(hook_file, install_dir)
    # Refuse to overwrite a concurrent editor's changes.
    if read_json(hook_file) != before:
        raise RuntimeError('hooks.json changed during installation; rerun after reviewing it')
    atomic_json(hook_file, after)
    atomic_json(install_dir / 'settings.json', {'codex_home': str(codex_home)})
    atomic_json(install_dir / 'manifest.json', {**plan, 'version': '0.1.0a1',
                                             'shortcuts': previous_manifest.get('shortcuts', [])})
    (install_dir / 'disabled').unlink(missing_ok=True)
    (install_dir / 'paused').unlink(missing_ok=True)
    (install_dir / 'stop.request').unlink(missing_ok=True)
    return plan


def uninstall(install_dir):
    install_dir = install_dir.resolve()
    manifest = read_json(install_dir / 'manifest.json')
    if not manifest or Path(manifest['install_dir']).resolve() != install_dir:
        raise ValueError('Valid installation manifest required')
    hook_file = Path(manifest['hook_file'])
    before = read_json(hook_file)
    after = hook_config.remove(before, install_dir / 'alerts.py')
    stop_runtime(install_dir, disable=True)
    if hook_file.exists():
        backup_hooks(hook_file, install_dir)
        if read_json(hook_file) != before:
            raise RuntimeError('hooks.json changed during uninstall; rerun')
        atomic_json(hook_file, after)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('install', 'uninstall'))
    parser.add_argument('--install-dir', type=Path, required=True)
    parser.add_argument('--codex-home', type=Path)
    parser.add_argument('--python-exe', type=Path, default=Path(sys.executable))
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    if args.action == 'install':
        if args.codex_home is None:
            parser.error('--codex-home is required for install')
        result = install_files(Path(__file__).parent, args.install_dir, args.codex_home,
                               args.python_exe, preview=args.preview)
    else:
        result = uninstall(args.install_dir)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
