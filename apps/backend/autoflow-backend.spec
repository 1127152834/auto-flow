# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


datas = [
    ('src/autoflow/infrastructure/filesystem/profile_environment.json', 'autoflow/infrastructure/filesystem'),
    ('src/autoflow/infrastructure/database/alembic.ini', 'autoflow/infrastructure/database'),
    ('src/autoflow/infrastructure/database/migrations', 'autoflow/infrastructure/database/migrations'),
    *collect_data_files('tzdata'),
    *collect_data_files('playwright'),
    *collect_data_files('ddddocr', includes=['*.onnx']),
    *copy_metadata('tzdata'),
    *copy_metadata('cloakbrowser'),
    *copy_metadata('keyring'),
    *copy_metadata('playwright'),
    *copy_metadata('langgraph'),
    *copy_metadata('langgraph-checkpoint'),
    *copy_metadata('langgraph-checkpoint-sqlite'),
    *copy_metadata('ddddocr'),
]
hiddenimports = [
    'autoflow.bootstrap.kernel_worker',
    'autoflow.bootstrap.test_browser_worker',
    'autoflow.bootstrap.workflow_worker',
    'autoflow.bootstrap.inspection_worker',
    'autoflow.providers.kernel.worker',
    'autoflow.providers.browser.worker',
    'autoflow.providers.browser.inspection_worker',
    'sqlalchemy.dialects.sqlite.pysqlite',
    'keyring.backends.macOS',
    'keyring.backends.macOS.api',
    'keyring.backends.Windows',
    *collect_submodules('cloakbrowser'),
    *collect_submodules('langgraph'),
    *collect_submodules('langgraph.checkpoint'),
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
