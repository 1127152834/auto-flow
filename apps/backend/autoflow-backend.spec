# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


datas = [
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
    'autoflow.providers.kernel.worker',
    'autoflow.providers.browser.worker',
    'sqlalchemy.dialects.sqlite.pysqlite',
    'keyring.backends.macOS',
    'keyring.backends.macOS.api',
    'keyring.backends.Windows',
    *collect_submodules('cloakbrowser'),
]


a = Analysis(
    ['src/autoflow/__main__.py'],
    pathex=['src'],
    binaries=[],
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
