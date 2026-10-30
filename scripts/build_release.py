"""Build an allowlisted, deterministic source ZIP. Never package installed state."""
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.1.0a1'
ROOT_FILES = ('alerts.py', 'hook_config.py', 'manage.py', 'install.ps1', 'uninstall.ps1',
              'README.md', 'NOTICE.md', 'CHANGELOG.md', 'CONTRIBUTING.md', 'SECURITY.md',
              'pyproject.toml', '.gitignore', '.gitattributes', 'LICENSE')
PATTERNS = ('docs/*.md', 'tests/test_*.py', 'tests/integration.ps1',
            'tests/gui_smoke.ps1',
            'scripts/build_release.py', '.github/workflows/*.yml',
            '.github/ISSUE_TEMPLATE/*.yml', '.github/pull_request_template.md')


def source_files(root=ROOT):
    files = {root / name for name in ROOT_FILES}
    for pattern in PATTERNS:
        files.update(root.glob(pattern))
    for path in files:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'Missing file or symlink in source list: {path.name}')
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def build(root=ROOT, output=None):
    output = output or root / 'dist'
    output.mkdir(parents=True, exist_ok=True)
    name = f'codex-desktop-alerts-{VERSION}'
    archive = output / (name + '.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in source_files(root):
            entry = zipfile.ZipInfo(name + '/' + path.relative_to(root).as_posix(), (1980,1,1,0,0,0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            # Normalize text line endings across Git checkout settings.
            bundle.writestr(entry, path.read_bytes().replace(b'\r\n', b'\n'))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / 'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
    return archive, digest


if __name__ == '__main__':
    archive, digest = build()
    print(f'{archive}\nSHA-256: {digest}')
