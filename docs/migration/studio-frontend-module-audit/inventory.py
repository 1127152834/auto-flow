"""Read-only source inventory; regex inventories are candidates, not reachability proofs."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'reference/WebRPA/frontend/src'
TARGET = ROOT / 'apps/desktop/src/renderer/domains/workflows'
manifest = json.loads((TARGET / 'source-manifest.json').read_text())
pairs = {row['source']: row for row in manifest}
rows = []
for path in sorted(SOURCE.rglob('*')):
    if not path.is_file():
        continue
    source = 'frontend/src/' + path.relative_to(SOURCE).as_posix()
    pair = pairs.get(source)
    rows.append({
        'source': source,
        'target': pair['target'] if pair else None,
        'manifestMapped': pair is not None,
        'targetExists': (ROOT / pair['target']).is_file() if pair else None,
        'sourceHashMatches': hashlib.sha256(path.read_bytes()).hexdigest() == pair['sha256'] if pair else None,
        'sameNameTargets': [str(p.relative_to(ROOT)) for p in TARGET.rglob(path.name)] if pair is None else [],
    })

def literals(text, pattern):
    return sorted(set(re.findall(pattern, text)))

socket_pattern = r"this\.socket(?:\?)?\.on\(['\"]([^'\"]+)['\"]"
emit_pattern = r"emitMockEvent\(['\"]([^'\"]+)['\"]"
original_events = literals((SOURCE / 'services/socket.ts').read_text(), socket_pattern)
current_events = literals((TARGET / 'events.ts').read_text(), socket_pattern)
producers = literals((TARGET / 'api/mock-server.ts').read_text(), emit_pattern)
result = {
    'scope': 'frontend/src files; literal socket subscriptions and direct mock event producers; no semantic parity claim',
    'sourceFiles': len(rows), 'manifestMapped': sum(r['manifestMapped'] for r in rows),
    'unmapped': sum(not r['manifestMapped'] for r in rows),
    'missingTargets': [r['source'] for r in rows if r['targetExists'] is False],
    'changedSourceHashes': [r['source'] for r in rows if r['sourceHashMatches'] is False],
    'originalLiteralSocketSubscriptions': original_events,
    'currentLiteralSocketSubscriptions': current_events,
    'removedLiteralSocketSubscriptions': sorted(set(original_events) - set(current_events)),
    'directMockEventProducers': producers,
    'subscriptionsWithoutDirectMockProducer': sorted(set(current_events) - set(producers)),
    'files': rows,
}
output = Path(__file__).with_name('inventory.json')
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k:v for k,v in result.items() if k != 'files'}, ensure_ascii=False, indent=2))
