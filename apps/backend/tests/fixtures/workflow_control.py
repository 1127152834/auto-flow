from copy import deepcopy
from uuid import uuid4

from autoflow.domain.workflows.catalog import node_catalog


def node(identifier, kind, **config):
    definition = next(item for item in node_catalog() if item['type'] == kind)
    return {'id': identifier, 'type': kind, 'label': definition['title'], 'config': {**deepcopy(definition['defaultConfig']), **config}}


def literal(value):
    return {'kind': 'literal', 'value': value}


def variable(name, *path):
    return {'kind': 'variable', 'name': name, 'path': list(path)}


def rule(left, operator='eq', right=None):
    return {'kind': 'value', 'operator': operator, 'left': left, 'right': literal(True) if right is None else right}


def payload(nodes, edges, variables=None):
    return {'document': {'id': str(uuid4()), 'name': '控制流测试', 'schemaVersion': 2, 'nodes': nodes,
        'edges': [{'id': f'e{i}', 'source': source, 'target': target, 'sourceHandle': handle, 'targetHandle': 'in'} for i, (source, handle, target) in enumerate(edges)],
        'variables': variables or []}, 'layout': {'nodes': {n['id']: {'x': i*240, 'y': 0} for i, n in enumerate(nodes)}, 'viewport': {'x': 0, 'y': 0, 'zoom': 1}}}


def accumulating_loop(mode='foreach'):
    return payload([
        node('loop', 'loop', endNodeId='end', mode=mode, source=literal([1, 2, 3]) if mode == 'foreach' else literal(3)),
        node('condition', 'condition', endNodeId='join', rules=[rule(variable('index'), 'eq', literal(2))]),
        node('skip', 'continue_loop'), node('join', 'condition_end', ownerNodeId='condition'),
        node('append', 'set_variable', variableName='result', operation='append', value=variable('index')),
        node('end', 'loop_end', ownerNodeId='loop'),
        node('after', 'set_variable', variableName='finished', value=literal(True)),
    ], [('loop', 'body', 'condition'), ('loop', 'done', 'after'), ('condition', 'true', 'skip'), ('condition', 'false', 'join'), ('join', 'out', 'append'), ('append', 'out', 'end')], [{'name': 'result', 'type': 'array', 'value': []}])
