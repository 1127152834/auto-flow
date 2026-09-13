"""Read-only B0 asset checks; never certifies application behavior."""
import hashlib
import json
import re
import struct
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESIGN = HERE.parents[1]
ROOT = DESIGN.parents[2]
manifest = json.loads((DESIGN / 'prototypes/manifest.json').read_text())
source_root = Path(manifest['sourceRoot'])
sources = json.loads((source_root / 'manifest.json').read_text())['entries']
source_ids = {entry['id'] for entry in sources}
assert len(sources) == len(source_ids) == 112
for entry in sources:
    assert hashlib.sha256((source_root / entry['file']).read_bytes()).hexdigest() == entry['sha256']
assets = manifest['assets']
assert len(assets) == 5 and len({a['file'] for a in assets}) == 5
boards = [board for asset in assets for board in asset['boardIds']]
assert len(boards) == len(set(boards)) == 22
for asset in assets:
    data = (DESIGN / 'prototypes' / asset['file']).read_bytes()
    assert data.startswith(b'\x89PNG\r\n\x1a\n')
    assert struct.unpack('>II', data[16:24]) == (asset['pixelWidth'], asset['pixelHeight'])
    assert hashlib.sha256(data).hexdigest() == asset['sha256']
    assert set(asset['sourceIds']) <= source_ids
    assert asset['businessEvidence'] is None and asset['userAcceptance'] == 'notExecuted'
ledger = json.loads((DESIGN / 'implementation-ledger.json').read_text())
assert len(ledger['tasks']) == 18
assert all(t['status'] == 'notStarted' and all(v is None for v in t['evidence'].values()) for t in ledger['tasks'])
documents = [DESIGN / 'prototype-briefs.md', DESIGN / 'prototype-interactions.md', *HERE.glob('*.md')]
links = 0
for document in documents:
    for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)', document.read_text()):
        target = target.strip('<>').split('#')[0]
        if not target or '://' in target:
            continue
        assert (document.parent / target).exists(), (document, target)
        links += 1
    assert set(re.findall(r'PMUI-[0-9a-f]{12}', document.read_text())) <= source_ids
for document in [*DESIGN.glob('*.json'), *HERE.glob('*.json'), *(DESIGN / 'prototypes').glob('*.json')]:
    json.loads(document.read_text())
changed = subprocess.check_output(['git', 'diff', '--name-only', '205fa64'], cwd=ROOT, text=True).splitlines()
untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
assert all(path.startswith(('docs/', '.ai/')) for path in [*changed, *untracked]), [*changed, *untracked]
subprocess.run(['git', 'diff', '--check', '205fa64'], cwd=ROOT, check=True)
print(json.dumps({'verifiedAt': datetime.now(timezone.utc).isoformat(), 'result': 'passed',
    'scope': 'B0 PNG integrity, source hashes, source IDs, links, JSON and milestone separation only',
    'checks': {'sourceHashes': 112, 'pngFiles': 5, 'boardIds': 22, 'futureTaskRecordsNotStarted': 18, 'businessPathsUnchanged': True, 'localLinks': links},
    'notExecuted': ['business tests', 'new Electron application verification', 'Windows', 'other architectures', 'packaged builds'],
    'visualReview': 'Separate human/model image inspection; not inferred by this script',
    'userAcceptance': 'notExecuted'}, ensure_ascii=False, indent=2))
