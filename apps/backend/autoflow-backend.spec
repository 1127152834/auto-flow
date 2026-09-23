# -*- mode: python ; coding: utf-8 -*-

import sys
from importlib.util import find_spec
from pathlib import Path

from PyInstaller.depend.bindepend import get_imports
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


datas = [
    ('src/autoflow/adapters/http/module-required-fields.json', 'autoflow/adapters/http'),
    ('src/autoflow/infrastructure/filesystem/profile_environment.json', 'autoflow/infrastructure/filesystem'),
    ('src/autoflow/infrastructure/database/alembic.ini', 'autoflow/infrastructure/database'),
    ('src/autoflow/infrastructure/database/migrations', 'autoflow/infrastructure/database/migrations'),
    *collect_data_files('tzdata'),
    *collect_data_files('playwright'),
    *copy_metadata('tzdata'),
    *copy_metadata('cloakbrowser'),
    *copy_metadata('keyring'),
    *copy_metadata('playwright'),
]
hiddenimports = [
    'autoflow.bootstrap.kernel_worker',
    'autoflow.bootstrap.test_browser_worker',
    'autoflow.bootstrap.workflow_worker',
    'autoflow.providers.kernel.worker',
    'autoflow.providers.browser.worker',
    'sqlalchemy.dialects.sqlite.pysqlite',
    'keyring.backends.macOS',
    'keyring.backends.macOS.api',
    'keyring.backends.Windows',
    *collect_submodules('cloakbrowser'),
]


# Intel cryptography can be built against Homebrew OpenSSL while Python uses an
# older libssl with the same basename. Prefer the extension's actual ABI pair.
binaries = []
if sys.platform == 'darwin':
    rust = find_spec('cryptography.hazmat.bindings._rust')
    if rust is not None and rust.origin:
        for _name, library in get_imports(rust.origin):
            if library and Path(library).name in {'libssl.3.dylib', 'libcrypto.3.dylib'}:
                binaries.append((library, '.'))


a = Analysis(
    ['src/autoflow/__main__.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='autoflow-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='autoflow-backend',
)
