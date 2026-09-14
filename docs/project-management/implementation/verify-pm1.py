"""PM1 coverage/document validation only; runtime evidence remains a separate report."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'docs/project-management/implementation'
coverage = json.loads((BASE / 'coverage.json').read_text())
design = ROOT / 'docs/project-management/design'
errors = []
counts = {}


def check(condition, message):
    if not condition:
        errors.append(message)


def ids(path, pattern):
    return set(re.findall(pattern, path.read_text()))


sources = {
    'features': ids(design / 'functional-structure.md', r'(?m)^### ((?:PM|OV|AU|RUN|ST|DT|ENV)-\d{2})\b'),
    'acceptance_scenarios': set().union(*(ids(design / name, r'\b(?:DATA-[A-Z0-9]+-\d{2}|FLOW-A\d{2}|XE-A\d{2})\b') for name in ('data-and-state-rules.md', 'data-flow-and-contracts.md', 'execution-and-environment.md'))),
    'execution_contracts_and_gates': ids(design / 'execution-and-environment.md', r'\bXE-[CG]\d{2}\b'),
}
packages = {p['id'] for p in coverage['delivery_packages']}
allowed = {'PM-01', 'PM-02', 'PM-03', 'OV-01'}
for group, expected in [('features', 48), ('acceptance_scenarios', 178), ('execution_contracts_and_gates', 25)]:
    rows = coverage[group]
    actual = {row['id'] for row in rows}
    check(len(actual) == len(rows) == expected, f'{group}: count/duplicate')
    check(actual == sources[group], f'{group}: source ID mismatch')
    counts[group] = len(rows)
    for row in rows:
        check(row['id'] in (ROOT / row['source']).read_text().splitlines()[row['source_line'] - 1], f"{row['id']}: source line")
        check(row['primary_package'] in packages and row['owner'] in coverage['ownership'], f"{row['id']}: ownership")
        check(set(row['completion_packages']) <= packages, f"{row['id']}: package reference")
        if row['id'] not in allowed:
            check(row['status'] == 'planned' and row['evidence'] == [], f"{row['id']}: future evidence changed")
        else:
            check(row['status'] == ('verified' if row['id'] == 'PM-02' else 'partially_verified'), f"{row['id']}: scope overclaim")
            check(bool(row['evidence']), f"{row['id']}: missing evidence")
counts['execution_contracts'] = sum(x.startswith('XE-C') for x in sources['execution_contracts_and_gates'])
counts['capability_gates'] = sum(x.startswith('XE-G') for x in sources['execution_contracts_and_gates'])
counts['delivery_packages'] = len(packages)
check(len(packages) == len(coverage['delivery_packages']) == 30, 'delivery package count')
graph = {m['id']: set(m['start_dependencies'] + m['exit_dependencies']) for m in coverage['milestones']}
for p in coverage['delivery_packages']:
    graph[p['id']] = set(p['start_dependencies'] + p['integration_after'])
    if p['milestone'] == 'PM1':
        check((ROOT / p['planned_test_file']).is_file(), f"{p['id']}: missing actual test")
visited, active = set(), set()


def visit(node):
    if node in active:
        check(False, f'dependency cycle: {node}')
        return
    if node in visited:
        return
    active.add(node)
    for dependency in graph[node]:
        check(dependency in graph, f'{node}: unknown dependency')
        if dependency in graph:
            visit(dependency)
    active.remove(node)
    visited.add(node)


for node in graph:
    visit(node)
for name in ['plan-verification.json', 'fixtures.json']:
    historical = subprocess.check_output(['git', 'show', f'9c361f4:docs/project-management/implementation/{name}'], cwd=ROOT)
    check((BASE / name).read_bytes() == historical, f'PM0 historical asset changed: {name}')
changed = subprocess.check_output(['git', 'diff', '--name-only', 'dbb01f5'], cwd=ROOT, text=True).splitlines()
changed += subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
link_count = json_count = 0
for name in set(changed):
    path = ROOT / name
    # The output report may be redirected here and is not an input document.
    if path.name == 'pm1-static-verification.json':
        continue
    if path.suffix == '.json' and path.is_file():
        json.loads(path.read_text()); json_count += 1
    if path.suffix != '.md' or not path.is_file():
        continue
    for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
        if target.startswith(('https:', 'http:', '#')):
            continue
        target = target.split('#', 1)[0]
        check((path.parent / target).exists(), f'{name}: broken link {target}')
        link_count += 1
counts.update(local_links=link_count, json_files=json_count)
check(subprocess.run(['git', 'diff', 'dbb01f5', '--check'], cwd=ROOT).returncode == 0, 'diff formatting')
print(json.dumps({'status': 'passed' if not errors else 'failed', 'kind': 'pm1-static-coverage-and-documents', 'counts': counts, 'errors': errors, 'not_proven': ['business behavior', 'Electron runtime', 'Windows', 'release packages']}, ensure_ascii=False, indent=2))
sys.exit(bool(errors))
