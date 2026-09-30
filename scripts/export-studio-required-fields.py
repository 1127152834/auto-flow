"""Extract final frozen schema literals without importing or executing WebRPA."""
import ast
import hashlib
import json
import pprint
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'reference/WebRPA/backend/app/services/ai_assistant_module_schemas.py'
AUTOFIX = SOURCE.with_name('ai_assistant_module_schemas_autofix.py')
LICENSE = ROOT / 'reference/WebRPA/LICENSE'
REVISION = 'WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb'
CAPABILITIES = ROOT / 'docs/migration/studio-frontend-completion/capabilities.json'
TARGET = ROOT / 'apps/desktop/src/renderer/domains/workflows/development/module-required-fields.json'
PRODUCTION_JSON = ROOT / 'apps/backend/src/autoflow/adapters/http/module-required-fields.json'
MANIFEST = ROOT / 'docs/migration/studio-frontend-completion/required-field-source-coverage.json'
PRODUCTION = ROOT / 'apps/backend/src/autoflow/domain/workflows/required_fields.py'
# AutoFlow-owned rules, reviewed against ProxyControlExecutor.execute and its UI.
# These nodes do not come from the frozen WebRPA source.
NATIVE_SCHEMAS = {
    name: {
        'required': ['locationId'] if name == 'proxy_change_location' else [],
        'conditional_required': {'field': 'target', 'default': 'current',
                                 'map': {'current': [], 'specified': ['proxyId']}},
        'desc': {'proxyId': '代理 ID／变量', 'locationId': '地点 ID／变量'},
    }
    for name in ('proxy_query', 'proxy_change_ip', 'proxy_change_location')
}

NATIVE_SCHEMAS['project_data'] = {
    'required': ['operation', 'arguments', 'variableName'],
    'conditional_required': {'field': 'operation', 'default': 'inputs', 'map': {
        operation: ['bindingProjectId', 'tableGrant']
        for operation in (
            'readRecord', 'queryRecords', 'queryTableSchema', 'createRecord',
            'updateRecord', 'deleteRecord', 'setRecordStatus', 'addField',
            'ensureField', 'modifyField', 'previewFieldChange', 'deleteField',
            'previewFieldDeletion',
        )
    } | {'inputs': []}},
    'desc': {
        'bindingProjectId': '绑定项目',
        'tableGrant': '授权数据表和字段',
        'arguments': '操作参数',
        'operation': '项目数据操作',
        'variableName': '结果变量',
    },
}

NATIVE_SCHEMAS['project_end'] = {
    'required': [],
    'desc': {
        'retainEnvironment': '环境保留策略',
        'name': '新环境名称',
        'recordTargets': '新增或已写记录的 RecordRef 列表',
    },
}

def _update_name(statement):
    if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
        raise TypeError('Frozen schema update must be a literal named-group update')
    call = statement.value
    if (not isinstance(call.func, ast.Attribute) or call.func.attr != 'update'
            or not isinstance(call.func.value, ast.Name) or call.func.value.id != '_ALL_SCHEMAS'
            or len(call.args) != 1 or not isinstance(call.args[0], ast.Name) or call.keywords):
        raise ValueError('Frozen schema update shape changed')
    return call.args[0].id


def _final_schemas():
    groups, schemas, merge_order = {}, {}, []
    autofix_tree = ast.parse(AUTOFIX.read_bytes())
    autofix = next(ast.literal_eval(node.value) for node in autofix_tree.body
                   if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                   and node.target.id == 'AUTOFIX_SCHEMAS')

    def merge(name):
        group = groups[name]
        if not isinstance(group, dict) or any(not isinstance(value, dict) for value in group.values()):
            raise ValueError(f'Frozen schema group is not a schema dictionary: {name}')
        schemas.update(group)
        merge_order.append(name)

    for node in ast.parse(SOURCE.read_bytes()).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            groups[node.target.id] = ast.literal_eval(node.value)
        elif isinstance(node, ast.For):
            if (not isinstance(node.target, ast.Name) or not isinstance(node.iter, ast.List)
                    or len(node.body) != 1 or node.orelse
                    or _update_name(node.body[0]) != node.target.id):
                raise ValueError('Frozen initial schema merge changed')
            for name in node.iter.elts:
                if not isinstance(name, ast.Name):
                    raise TypeError('Frozen initial schema groups must be named literals')
                merge(name.id)
        elif isinstance(node, ast.Try):
            # This is the source's sole optional import. The frozen patch exists;
            # apply its literal data at exactly this position, before manual fixes.
            imported = node.body[0]
            if (len(node.body) != 2 or not isinstance(imported, ast.ImportFrom)
                    or imported.module != 'app.services.ai_assistant_module_schemas_autofix'
                    or len(imported.names) != 1 or imported.names[0].name != 'AUTOFIX_SCHEMAS'
                    or imported.names[0].asname or _update_name(node.body[1]) != 'AUTOFIX_SCHEMAS'):
                raise ValueError('Frozen schema patch import changed')
            groups['AUTOFIX_SCHEMAS'] = autofix
            merge('AUTOFIX_SCHEMAS')
        elif isinstance(node, ast.Expr) and not isinstance(node.value, ast.Constant):
            merge(_update_name(node))
        elif not isinstance(node, (ast.Expr, ast.ImportFrom, ast.FunctionDef)):
            raise TypeError(f'Unsupported frozen schema statement: {type(node).__name__}')
    if 'AUTOFIX_SCHEMAS' not in merge_order:
        raise ValueError('Frozen schema patch was not merged')
    return schemas, merge_order


def extract():
    schemas, merge_order = _final_schemas()
    retained = {entry['type'] for entry in json.loads(CAPABILITIES.read_text(encoding='utf-8'))} | NATIVE_SCHEMAS.keys()
    if len(retained) != 213 + len(NATIVE_SCHEMAS):
        raise ValueError(f'Approved source and native node scope changed: {len(retained)}')
    if schemas.keys() & NATIVE_SCHEMAS.keys():
        raise ValueError('Native metadata must not override frozen source rules')
    schemas.update(NATIVE_SCHEMAS)
    covered = sorted(retained & schemas.keys())
    missing = sorted(retained - schemas.keys())
    if missing:
        raise ValueError(f'Source and native metadata do not cover approved nodes: {missing}')
    result = {'schemaRevision': REVISION, 'coveredModules': covered, 'requiredFields': {}, 'conditionalRequired': {}, 'fieldLabels': {}}
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
    result['fieldLabels']['python_script']['useBuiltinPython'] = 'True 使用 AutoFlow 随包 Python；False 可通过 pythonPath 指定已安装的 Python'
    sources = [{'source': path.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in (SOURCE, AUTOFIX)]
    manifest = {
        **sources[0], 'sources': sources, 'sourceRevision': REVISION,
        'nativeModules': sorted(NATIVE_SCHEMAS),
        'nativeSources': ['apps/backend/src/autoflow/application/workflows/executors/proxy_control.py',
                          'apps/backend/src/autoflow/providers/browser/project_graph.py',
                          'apps/backend/src/autoflow/application/project_runs/worker_capabilities.py'],
        'license': {'path': LICENSE.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(LICENSE.read_bytes()).hexdigest()},
        'modifications': ['Read final literal groups in frozen merge order, including AUTOFIX and later manual overrides.',
                          'Filter frozen metadata to 213 retained source nodes; add AutoFlow proxy and canonical project data/End rules for the approved native scope.',
                          'Describe AutoFlow bundled Python instead of the source Python313 environment.'],
        'mergeOrder': merge_order, 'approvedCount': len(retained), 'coveredCount': len(covered),
        'covered': covered, 'uncovered': missing,
        'boundary': 'Frozen source plus explicit AutoFlow native metadata coverage, not complete node configuration validation.',
    }
    return result, manifest


def production_text(metadata, manifest):
    sources = '\n'.join(f'# Source: {item["source"]} (SHA-256 {item["sha256"]})' for item in manifest['sources'])
    return (f'"""Generated Studio field metadata from {REVISION}."""\n'
            f'{sources}\n# License: reference/WebRPA/LICENSE; preserve original license and provenance.\n'
            '# Adaptation: final source merge order, approved-scope filtering and explicit coverage.\n'
            '# Regenerate: python3 scripts/export-studio-required-fields.py\n'
            'from typing import Any\n\n'
            'MODULE_REQUIRED_FIELDS: dict[str, Any] = '
            + pprint.pformat(metadata, width=100, sort_dicts=False) + '\n')


if __name__ == '__main__':
    import sys
    metadata, manifest = extract()
    outputs = [(PRODUCTION_JSON, json.dumps(metadata, ensure_ascii=False, indent=2) + '\n'),
               (TARGET, json.dumps(metadata, ensure_ascii=False, indent=2) + '\n'),
               (MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'),
               (PRODUCTION, production_text(metadata, manifest))]
    for target, text in outputs:
        if '--check' in sys.argv:
            if not target.exists() or target.read_text(encoding='utf-8') != text:
                raise SystemExit(f'Generated metadata is stale: {target}')
        else:
            target.write_text(text, encoding='utf-8')
