# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
    get_package_paths,
)

_, torchvision_path = get_package_paths('torchvision')
torchvision_binaries = (
    collect_dynamic_libs('torchvision')
    + collect_dynamic_libs('ctranslate2')
    + collect_dynamic_libs('mediapipe')
    + [
    (str(path), 'torchvision')
    for path in Path(torchvision_path).glob('*_stable.so')
    ]
)

datas = [
    ('src/autoflow/infrastructure/filesystem/profile_environment.json', 'autoflow/infrastructure/filesystem'),
    ('src/autoflow/infrastructure/database/alembic.ini', 'autoflow/infrastructure/database'),
    ('src/autoflow/infrastructure/database/migrations', 'autoflow/infrastructure/database/migrations'),
    *collect_data_files('tzdata'),
    *collect_data_files('playwright'),
    *collect_data_files('ddddocr', includes=['*.onnx']),
    *collect_data_files('easyocr'),
    *collect_data_files('face_recognition_models'),
    *collect_data_files('faster_whisper'),
    *collect_data_files('mediapipe'),
    ('src/autoflow/resources/mediapipe/hand_landmarker.task', 'autoflow/resources/mediapipe'),
    ('../../reference/WebRPA/backend/models/ocr/easyocr/*.pth', 'autoflow/resources/easyocr'),
    *copy_metadata('tzdata'),
    *copy_metadata('cloakbrowser'),
    *copy_metadata('keyring'),
    *copy_metadata('playwright'),
    *copy_metadata('langgraph'),
    *copy_metadata('langgraph-checkpoint'),
    *copy_metadata('langgraph-checkpoint-sqlite'),
    *copy_metadata('ddddocr'),
    *copy_metadata('easyocr'),
    *copy_metadata('face-recognition'),
    *copy_metadata('face-recognition-models'),
    *copy_metadata('faster-whisper'),
    *copy_metadata('mediapipe'),
    *copy_metadata('ctranslate2'),
    *copy_metadata('huggingface-hub'),
    *copy_metadata('tokenizers'),
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
    *collect_submodules('easyocr'),
    *collect_submodules('face_recognition'),
    *collect_submodules('faster_whisper'),
    *collect_submodules('mediapipe'),
]


a = Analysis(
    ['src/autoflow/__main__.py'],
    pathex=['src'],
    binaries=torchvision_binaries,
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
