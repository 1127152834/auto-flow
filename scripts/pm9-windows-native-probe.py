"""Native experiment, not production admission: test held-handle rename semantics."""
import ctypes
import json
import os
import sys
import tempfile
from ctypes import wintypes
from pathlib import Path

if sys.platform != 'win32':
    raise SystemExit('Native Windows required')

kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
kernel.CreateFileW.restype = wintypes.HANDLE
kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
kernel.SetFileInformationByHandle.restype = wintypes.BOOL
kernel.CloseHandle.argtypes = [wintypes.HANDLE]

class Rename(ctypes.Structure):
    _fields_ = [('flags', wintypes.DWORD), ('root', wintypes.HANDLE), ('length', wintypes.DWORD), ('name', wintypes.WCHAR * 1024)]

def opened(path, access, share, flags=0):
    handle = kernel.CreateFileW(str(path), access, share, None, 3, flags, None)
    if handle == wintypes.HANDLE(-1).value: raise ctypes.WinError(ctypes.get_last_error())
    return handle

result = {'platform': sys.platform, 'purpose': 'S4 rename-with-held-target feasibility; does not enable output'}
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    for flags in [1, 3]:
        target, staged = root / f'target-{flags}', root / f'stage-{flags}'
        target.write_bytes(b'original'); staged.write_bytes(b'new')
        # Existing target denies WRITE and DELETE to other handles.
        old = opened(target, 0x80000000, 1)
        stage = opened(staged, 0x80000000 | 0x40000000 | 0x10000, 1)
        try:
            rename = Rename(); rename.flags = flags; rename.name = str(target)
            rename.length = len(str(target).encode('utf-16-le'))
            ok = bool(kernel.SetFileInformationByHandle(stage, 22, ctypes.byref(rename), Rename.name.offset + rename.length))
            result[f'rename_flags_{flags}'] = {'success': ok, 'error': 0 if ok else ctypes.get_last_error()}
        finally:
            kernel.CloseHandle(stage); kernel.CloseHandle(old)
        result[f'rename_flags_{flags}']['value'] = target.read_text()
    parent = root / 'held'; parent.mkdir()
    handle = opened(parent, 0x80000000, 1 | 2, 0x02000000 | 0x00200000)
    try:
        try: parent.rename(root / 'moved')
        except OSError as error: result['held_parent_rename'] = {'denied': True, 'error': error.winerror}
        else: result['held_parent_rename'] = {'denied': False}
    finally: kernel.CloseHandle(handle)
Path(os.environ.get('PM9_PROBE_OUTPUT', 'pm9-native-probe.json')).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
print(json.dumps(result, indent=2))
