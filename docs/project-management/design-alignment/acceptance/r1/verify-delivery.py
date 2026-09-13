"""Static R1 evidence integrity only; never substitutes for application/user tests."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'apps/desktop').is_dir())
BASE = HERE.parent.parent
report = json.loads((HERE / 'verification.json').read_text())
ledger = json.loads((BASE / 'implementation-ledger.json').read_text())
source_ids = {e['id'] for e in json.loads((BASE / 'coverage.json').read_text())['entries']}
expected = {f'R1-{n:02}' for n in range(1, 6)}
r1 = [t for t in ledger['tasks'] if t['taskId'].startswith('R1-')]
assert len(r1) == 5 and {t['taskId'] for t in r1} == expected
for task in r1:
    assert task['status'] == 'implementedAndVerified'
    assert task['userAcceptance'] == 'pending'
    assert task['sourceIds'] and set(task['sourceIds']) <= source_ids
    for field in ('automatic', 'electron'):
        assert (BASE / task['evidence'][field]).is_file()
    assert task['evidence']['windows'] is None
    for file in task['files']:
        assert (ROOT / file['path']).exists(), file
for task in ledger['tasks']:
    if not task['taskId'].startswith(('R2-', 'R3-')):
        continue
    assert task['status'] == 'notStarted' and task['commit'] is None
    assert all(value is None for value in task['evidence'].values())
run = json.loads((HERE / report['application']['r1']).read_text())
assert run['result'] == 'passed' and run['commandErrors'] == []
assert run['provenance']['gitHead'] == report['validatedCodeCommit']
script = ROOT / 'scripts/qa-project-alignment-r1.mjs'
assert run['provenance']['scriptSha256'] == hashlib.sha256(script.read_bytes()).hexdigest()
for path, digest in report['assetsSha256'].items():
    assert hashlib.sha256((HERE / path).read_bytes()).hexdigest() == digest
for check in report['checks']:
    assert check['result'] == 'passed' and (HERE / check['log']).is_file()
for key in ('pm2Data', 'pm2Detail'):
    assert json.loads((HERE / report['application'][key]).read_text())['result'] == 'passed'
changed = subprocess.check_output(['git', 'diff', '--name-only', '1e79c7b'], cwd=ROOT, text=True).splitlines()
assert not any(p.startswith(('apps/backend/', 'apps/desktop/src/main/', 'apps/desktop/src/preload/')) or p.endswith('/generated.ts') for p in changed)
assert not any(p.startswith('docs/project-management/design-alignment/acceptance/b0/') for p in changed)
for file in HERE.rglob('*.json'):
    json.loads(file.read_text())
links = 0
for doc in HERE.glob('*.md'):
    for target in re.findall(r'\]\(([^)]+)\)', doc.read_text()):
        if '://' in target or target.startswith('#'):
            continue
        assert (doc.parent / target.split('#')[0]).exists(), (doc.name, target)
        links += 1
assert (HERE / 'manual-test.md').read_text().count('| 未执行 |') == 9
subprocess.run(['git', 'diff', '--check', '1e79c7b'], cwd=ROOT, check=True)
output = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'result': 'passed',
          'scope': 'R1 ledger, source IDs, evidence files/hashes, local links and change boundary only',
          'checks': {'r1Tasks': len(r1), 'futureTasksUnchanged': len(ledger['tasks']) - len(r1),
                     'localLinks': links, 'screenshots': len(report['assetsSha256']), 'businessBoundary': True},
          'userAcceptance': 'notExecuted', 'windows': 'notExecuted'}
(HERE / 'static-verification.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(output, ensure_ascii=False))
