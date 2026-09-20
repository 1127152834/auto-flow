"""Extract the frozen metadata literals without importing or executing the source backend."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'reference/WebRPA/backend/app/services/ai_assistant_module_schemas.py'
CAPABILITIES = ROOT / 'docs/migration/studio-frontend-completion/capabilities.json'
TARGET = ROOT / 'apps/desktop/src/renderer/domains/workflows/development/module-required-fields.json'
MANIFEST = ROOT / 'docs/migration/studio-frontend-completion/required-field-source-coverage.json'


def extract():
    raw = SOURCE.read_bytes()
    tree = ast.parse(raw)
    names = {'BROWSER_SCHEMAS', 'CONTROL_SCHEMAS', 'DATA_SCHEMAS', 'LIST_SCHEMAS', 'AI_NET_SCHEMAS', 'UTIL_SCHEMAS'}
    schemas = {}
    found = set()
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id in names:
            schemas.update(ast.literal_eval(node.value))
            found.add(node.target.id)
    if found != names:
        raise ValueError('Frozen schema literal groups changed')
    retained = {entry['type'] for entry in json.loads(CAPABILITIES.read_text(encoding='utf-8'))}
    if len(retained) != 227:
        raise ValueError(f'Approved 227-node scope changed: {len(retained)}')
    covered = sorted(retained & schemas.keys())
    result = {'schemaRevision': 'WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb', 'coveredModules': covered, 'requiredFields': {}, 'conditionalRequired': {}, 'fieldLabels': {}}
    for name in covered:
        schema = schemas[name]
        defaults = schema.get('defaults') or {}
        required = [field for field in schema.get('required', []) if field not in defaults]
        if required:
            result['requiredFields'][name] = required
        labels = {key: value for key, value in (schema.get('desc') or {}).items() if isinstance(value, str) and value.strip()}
        if labels:
            result['fieldLabels'][name] = labels
        condition = schema.get('conditional_required')
        if isinstance(condition, dict) and condition.get('map'):
            result['conditionalRequired'][name] = {'field': condition['field'], 'default': condition.get('default'), 'map': {key: [field for field in fields if field not in defaults] for key, fields in condition['map'].items()}}
    manifest = {'source': SOURCE.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(raw).hexdigest(), 'approvedCount': len(retained), 'coveredCount': len(covered), 'covered': covered, 'uncovered': sorted(retained - schemas.keys()), 'boundary': 'Source metadata coverage only, not complete node configuration validation.'}
    return result, manifest


if __name__ == '__main__':
    import sys
    for target, content in zip([TARGET, MANIFEST], extract()):
        text = json.dumps(content, ensure_ascii=False, indent=2) + '\n'
        if '--check' in sys.argv:
            if not target.exists() or target.read_text(encoding='utf-8') != text:
                raise SystemExit(f'Generated metadata is stale: {target}')
        else:
            target.write_text(text, encoding='utf-8')
