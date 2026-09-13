"""Validate design evidence only; does not run or certify product behavior."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = Path('/Users/zhangtiancheng/Documents/projects/autoflow/docs/references/project-management-prototypes-2026-09-13')
MANIFEST = SOURCE / 'manifest.json'
manifest = json.loads(MANIFEST.read_text())
entries = manifest['entries']
assert len(entries) == len({e['id'] for e in entries}) == 112
reviews = {}
for name in ('overview-automation-statistics', 'runs-environments', 'projects-data-shared'):
    document = json.loads((HERE / f'{name}.json').read_text())
    for entry in document['entries']:
        identity = entry['id']
        assert identity not in reviews, f'Duplicate reviewed image: {identity}'
        assert entry.get('imageInspected', entry.get('viewedOriginal')) is True
        reviews[identity] = (name, entry)
expected = {e['id'] for e in entries if e['section'] != 'history'}
assert reviews.keys() == expected, f'Coverage differs: {reviews.keys() ^ expected}'
assert len(reviews) == 93
assert sum(e['section'] == 'latest' for e in entries) == 91
assert sum(e['section'] == 'history' for e in entries) == 19
assert sum(e['section'] not in {'latest', 'history'} for e in entries) == 2
coverage = []
for entry in entries:
    source_file = SOURCE / entry['file']
    assert source_file.is_file(), source_file
    digest = hashlib.sha256(source_file.read_bytes()).hexdigest()
    assert digest == entry['sha256'], source_file
    review = reviews.get(entry['id'])
    if review:
        name, observed = review
        assert observed.get('file', observed.get('path')) == entry['file']
        assert observed['module'] == entry['module']
    record = {k: entry[k] for k in ('id', 'module', 'title', 'file', 'section', 'approval', 'sha256')}
    record.update({
        'visuallyInspected': bool(review),
        'reviewDocument': f'{review[0]}.md' if review else None,
        'selection': 'excluded-history' if not review else 'reference-to-adapt',
        'businessVerification': None,
    })
    if entry['id'] == 'PMUI-d81799ae026b':
        record['selection'] = 'excluded-external-sqlite-source'
    elif entry['id'] == 'PMUI-6fd26487657c':
        record['selection'] = 'alternative-not-recommended-layout'
    elif entry['id'] == 'PMUI-d7724054d211':
        record['selection'] = 'recommended-candidate-not-approved'
    elif entry['id'] == 'PMUI-3a2ef6f57afe':
        record['observedTitle'] = '持久环境已删除（结果页）'
        record['sourceTitleMismatch'] = True
        record['missingDesign'] = 'ALIGN-ENV-01'
    coverage.append(record)

new_ids = ['ALIGN-AUTO-01', 'ALIGN-AUTO-02', 'ALIGN-DATA-01', 'ALIGN-DATA-02', 'ALIGN-DATA-03', 'ALIGN-ENV-01']
spec = ROOT / 'docs/superpowers/specs/2026-09-13-project-management-prototype-alignment-design.md'
assert all(identity in spec.read_text() for identity in new_ids)
checked_links = 0
for document in [*HERE.glob('*.md'), spec]:
    contents = document.read_text()
    for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)', contents):
        target = target.strip('<>').split('#')[0]
        if not target or '://' in target:
            continue
        resolved = Path(target) if target.startswith('/') else document.parent / target
        assert resolved.exists() or (resolved.parent.resolve() == HERE and resolved.name in {'coverage.json', 'verification.json'}), f'{document.name}: missing link {target}'
        checked_links += 1
    for identity in re.findall(r'PMUI-[0-9a-f]{12}', contents):
        assert identity in {e['id'] for e in entries}, f'Unknown source ID {identity}'

payload = {
    'date': '2026-09-13', 'status': 'proposed-design-not-business-acceptance',
    'sourceManifest': str(MANIFEST),
    'manifestSha256': hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
    'counts': {'manifest': 112, 'latestInspected': 91, 'sameDayCandidatesInspected': 2, 'historyExcluded': 19},
    'entries': coverage,
    'missingArtboards': [{'id': identity, 'status': 'proposed-not-generated'} for identity in new_ids],
}
(HERE / 'coverage.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
for document in HERE.glob('*.json'):
    json.loads(document.read_text())
report = {
    'verifiedAt': datetime.now(timezone.utc).isoformat(),
    'implementationBaseline': '88efe0740e7cb9e83ad2a2455241ffab50465853',
    'scope': 'Design source coverage, file hashes, references and JSON structure only',
    'command': 'python3 docs/project-management/design-alignment/verify-alignment.py',
    'result': 'passed',
    'checks': {'uniqueManifestIds': 112, 'inspectedIds': 93, 'hashesVerified': 112, 'localMarkdownLinks': checked_links, 'missingArtboardDefinitions': 6},
    'inspectedByModule': dict(sorted(Counter(e['module'] for e in coverage if e['visuallyInspected']).items())),
    'limits': ['Source image inspection is documented manual observation, not inferred by this validator.', 'No new high-fidelity artboards generated.', 'No business implementation, automated product tests or new Electron acceptance run.', 'Windows, other architectures and packaged application acceptance not executed.', 'Previous audit and PM0/PM1/PM2 reports are historical and not overwritten.'],
}
(HERE / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
