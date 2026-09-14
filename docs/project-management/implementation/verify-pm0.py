"""只读核验 PM0 文档与合成样例；不导入应用、不运行数据库、不证明业务行为。"""
from pathlib import Path
import json
import re
import subprocess
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'docs/project-management/implementation'
errors = []
counts = {}


def check(condition, message):
    if not condition:
        errors.append(message)


def ids(text, pattern):
    return set(re.findall(pattern, text))


def unique(items, label):
    values = [x['id'] for x in items]
    check(len(values) == len(set(values)), f'{label}: duplicate IDs')
    return set(values)


def uuid(value, label):
    try:
        check(str(UUID(value)) == value, f'{label}: noncanonical UUID')
    except (ValueError, TypeError, AttributeError):
        check(False, f'{label}: invalid UUID')


coverage = json.loads((BASE / 'coverage.json').read_text())
fixtures = json.loads((BASE / 'fixtures.json').read_text())
design = ROOT / 'docs/project-management/design'
source_sets = {
    'features': ids((design / 'functional-structure.md').read_text(), r'(?m)^### ((?:PM|OV|AU|RUN|ST|DT|ENV)-\d{2})\b'),
    'acceptance_scenarios': set().union(*(ids((design / name).read_text(), r'\b(?:DATA-[A-Z0-9]+-\d{2}|FLOW-A\d{2}|XE-A\d{2})\b') for name in ('data-and-state-rules.md', 'data-flow-and-contracts.md', 'execution-and-environment.md'))),
    'execution_contracts_and_gates': ids((design / 'execution-and-environment.md').read_text(), r'\bXE-[CG]\d{2}\b'),
}
package_ids = unique(coverage['delivery_packages'], 'packages')
milestone_ids = unique(coverage['milestones'], 'milestones')
for group, expected_count in [('features', 48), ('acceptance_scenarios', 178), ('execution_contracts_and_gates', 25)]:
    items = coverage[group]
    actual = unique(items, group)
    counts[group] = len(actual)
    check(len(actual) == expected_count, f'{group}: count changed')
    check(actual == source_sets[group], f'{group}: source mismatch {actual ^ source_sets[group]}')
    for item in items:
        check(item['id'] in (ROOT / item['source']).read_text().splitlines()[item['source_line'] - 1], f"{item['id']}: source line")
        check(item.get('primary_package') in package_ids, f"{item['id']}: missing package")
        check(item.get('owner') in coverage['ownership'], f"{item['id']}: missing owner")
        check(bool(item.get('planned_test_file')) and item['planned_test_file'].startswith('apps/'), f"{item['id']}: test target")
        check(bool(item.get('acceptance_methods')) and bool(item.get('completion_packages')), f"{item['id']}: acceptance mapping")
        check(set(item['completion_packages']) <= package_ids, f"{item['id']}: completion package")
        check(item.get('status') == 'planned' and item.get('evidence') == [], f"{item['id']}: PM0 cannot claim business passed")

# Check milestone and package integration dependencies, including targets and cycles.
graph = {}
for m in coverage['milestones']:
    deps = set(m['start_dependencies']) | set(m['exit_dependencies'])
    check(deps <= milestone_ids, f"{m['id']}: missing milestone dependency")
    graph[m['id']] = deps
for p in coverage['delivery_packages']:
    deps = set(p['start_dependencies']) | set(p['integration_after'])
    check(deps <= milestone_ids | package_ids, f"{p['id']}: missing package dependency")
    check(p['owner'] in coverage['ownership'], f"{p['id']}: missing owner")
    graph[p['id']] = deps
visited, active = set(), set()

def visit(node):
    if node in active:
        check(False, f'dependency cycle: {node}')
        return
    if node in visited:
        return
    active.add(node)
    for dep in graph.get(node, ()):
        visit(dep)
    active.remove(node)
    visited.add(node)

for node in graph:
    visit(node)

contracts = (BASE / 'contracts.md').read_text()
cards = re.split(r'(?m)^### (XE-C\d{2}) · ', contracts)[1:]
card_ids = cards[::2]
check(len(card_ids) == 18 and set(card_ids) == {f'XE-C{i:02}' for i in range(1, 19)}, '18 unique contract cards')
for card_id, body in zip(card_ids, cards[1::2]):
    for field in ('调用方', '输入 / 输出', '操作身份 / 前提', '错误 / 事务边界', '查询与恢复'):
        check(field in body, f'{card_id}: missing {field}')
counts['execution_contracts'] = len(card_ids)
counts['capability_gates'] = len([x for x in source_sets['execution_contracts_and_gates'] if x.startswith('XE-G')])
api = (BASE / 'api-contracts.md').read_text()
routes = re.findall(r'(?m)^\| `(GET|POST|PUT|PATCH|DELETE) ([^`]+)` \|', api)
check(len(routes) == len(set(routes)), 'duplicate method/path')
check(not any('/runs' in path for method, path in routes), 'project-owned Run route')
counts['route_rows'] = len(routes)

fixture_ids = unique(fixtures['fixtures'], 'fixtures')
scenario_ids = unique(fixtures['scenarios'], 'fixture scenarios')
check(fixture_ids == {f'FX-{i:02}' for i in range(1, 8)}, 'FX-01 through FX-07 required')
check(len(unique(fixtures['representativeWorkflows'], 'workflows')) == 3, 'three representative workflows')
all_source_ids = set().union(*source_sets.values())
for item in fixtures['scenarios'] + fixtures['representativeWorkflows']:
    check(set(item['fixtures']) <= fixture_ids, f"{item['id']}: fixture reference")
    check(set(item['acceptanceIds']) <= all_source_ids, f"{item['id']}: acceptance reference")
    check(set(item['deliveryPackages']) <= package_ids, f"{item['id']}: package reference")
    check(bool(item['steps']) and bool(item['expectedFacts']), f"{item['id']}: missing steps/results")
    check(item['status'] == 'planned' and item['evidence'] == [], f"{item['id']}: evidence must be empty")
for f in fixtures['fixtures']:
    check(set(f['scenarios']) <= scenario_ids, f"{f['id']}: scenario reference")
    known_refs = {json.dumps(row['ref'], sort_keys=True) for t in f['tables'] for row in t['records']}
    for t in f['tables']:
        keys = {field['key'] for field in t['fields']}
        check(len(keys) == len(t['fields']), f"{f['id']}: duplicate field")
        for key in ('projectId', 'tableId', 'datasetGeneration'):
            uuid(t[key], f"{f['id']}.{key}")
        known_status = {x['statusId'] for x in t['statusCatalog']}
        row_keys = set()
        for row in t['records']:
            ref = row['ref']
            check(all(ref[k] == t[k] for k in ('projectId', 'tableId', 'datasetGeneration')), f"{f['id']}: row scope")
            check(set(row['values']) <= keys, f"{f['id']}: value without field")
            check(all(value is None or type(value) in (str, int, float, bool) for value in row['values'].values()), f"{f['id']}: nonscalar business value")
            check(row['statusId'] is None or row['statusId'] in known_status, f"{f['id']}: status without catalog")
            key = ref['recordKey']; canonical = (key['type'], key['value'])
            check(canonical not in row_keys, f"{f['id']}: duplicate record identity")
            row_keys.add(canonical)
            check(isinstance(key['value'], str), f"{f['id']}: record key wire encoding")
            if key['type'] == 'integer':
                check(re.fullmatch(r'0|-?[1-9][0-9]*', key['value']) is not None and abs(int(key['value'])) <= 2**53 - 1, 'integer key canonical/safe')
            elif key['type'] == 'uuid':
                uuid(key['value'], 'system record key')
            else:
                check(key['type'] == 'text' and bool(key['value']), 'text record key')
            for target in row['recordSlots'].values():
                check(target is None or json.dumps(target, sort_keys=True) in known_refs, f"{f['id']}: invalid record slot")
            check(all(type(row[k]) is int and row[k] >= 0 for k in ('contentRevision', 'statusRevision', 'linkRevision')), 'revision encoding')
    for env in f.get('environments', []):
        check(type(env['contentGeneration']) is int and env['contentGeneration'] >= 1, 'environment generation')
# Preserve the fixed source examples; these are data checks, not engine behavior.
f4 = next(f for f in fixtures['fixtures'] if f['id'] == 'FX-04')['tables'][0]['records'][0]
check([f4[k] for k in ('contentRevision', 'statusRevision', 'linkRevision')] == [7, 3, 2] and f4['values']['备注'] == '旧值', 'FX-04 fixed baseline')
f6 = next(f for f in fixtures['fixtures'] if f['id'] == 'FX-06')['tables'][0]['records']
check([(x['ref']['recordKey']['type'], x['ref']['recordKey']['value']) for x in f6] == [('text', '001'), ('text', '1'), ('integer', '1')], 'FX-06 typed identities')
counts.update(fixtures=len(fixture_ids), fixture_scenarios=len(scenario_ids), representative_workflows=3, delivery_packages=len(package_ids))

# Validate local Markdown links in this delivery, including newly added documents.
md_files = list(BASE.glob('*.md')) + [ROOT / 'docs/superpowers/plans/2026-09-13-project-management-pm0.md', ROOT / 'docs/PROJECT_STRUCTURE.md']
md_files += list((ROOT / '.ai').glob('*/2026-09-13-project-management-pm0*.md'))
links = 0
for path in md_files:
    for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
        if target.startswith(('http:', 'https:', '#')):
            continue
        target = target.split('#', 1)[0]
        check((path.parent / target).exists(), f'{path.relative_to(ROOT)}: broken link {target}')
        links += 1
counts['local_links_checked'] = links
result = subprocess.run(['git', 'diff', '--check'], cwd=ROOT, capture_output=True, text=True)
check(result.returncode == 0, f'git diff --check: {result.stdout}{result.stderr}')
changed = subprocess.check_output(['git', 'diff', '--name-only', '349c4be'], cwd=ROOT, text=True).splitlines()
untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
check(all(path.startswith(('docs/', '.ai/')) for path in changed + untracked), 'change outside documentation scope')
history = subprocess.check_output(['git', 'diff', '--name-only', '906deda', '--', 'docs/project-management/design/'], cwd=ROOT, text=True)
check(not history, 'historical design changed')
print(json.dumps({'status': 'passed' if not errors else 'failed', 'kind': 'pm0-static-document-validation', 'counts': counts, 'errors': errors, 'not_proven': ['business behavior', 'runtime interfaces', 'UI', 'CloakBrowser', 'live Sheets', 'Windows/macOS acceptance']}, ensure_ascii=False, indent=2))
sys.exit(bool(errors))
