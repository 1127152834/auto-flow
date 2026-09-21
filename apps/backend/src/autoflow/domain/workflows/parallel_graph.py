"""The structured fork shape accepted by the shared Runtime."""
from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from .graph import ExecutionGraph
from .models import WorkflowError


@dataclass(frozen=True)
class StructuredFork:
    join_id: str
    branches: dict[str, set[str]]
    outputs: dict[str, dict[str, str]]


def structured_fork(graph: ExecutionGraph, node_id: str) -> StructuredFork:
    def reject(detail: str) -> NoReturn:
        raise WorkflowError('WORKFLOW_NOT_RUNNABLE', f'并行节点 {node_id}: {detail}', 422)

    node = graph.nodes[node_id]
    config = node.data.get('config', node.data)
    declaration = config.get('parallel')
    if node.type != 'set_variable' or not isinstance(declaration, dict) or set(declaration) != {'joinNodeId', 'outputs'}:
        reject('结构化 fork 必须在设置变量节点声明 joinNodeId 和 outputs')
    join = declaration['joinNodeId']
    roots = graph.get_next_nodes(node_id)
    if not isinstance(join, str) or join not in graph.nodes or join in [node_id, *roots] or len(roots) < 2:
        reject('需要两个以上分支和独立唯一汇合节点')
    branches: dict[str, set[str]] = {}
    owned: set[str] = set()
    for root in roots:
        members: set[str] = set()
        pending = [root]
        while pending:
            current = pending.pop()
            if current == join or current in members:
                continue
            if current == node_id or current not in graph.nodes:
                reject('分支回到 fork 或引用缺失节点')
            members.add(current)
            pending.extend(graph.full_successors(current))
        if members & owned or join not in graph._forward_reachable(root):
            reject('分支交叉或不能到达声明的汇合节点')
        loop_members = set().union(*(graph.loop_body_scope(identity) for identity in members if identity in graph.loop_branches))
        for identity in members:
            if graph.nodes[identity].type == 'project_end':
                reject('End 必须在并行分支汇合后执行')
            if not graph.full_successors(identity) and identity not in loop_members:
                reject('分支存在不经过汇合的出口')
            if graph.nodes[identity].type in {'break_loop', 'continue_loop'} and identity not in loop_members:
                reject('分支只能控制自己拥有的循环')
            if any(source not in members and source != node_id for source in graph.get_prev_nodes(identity)):
                reject('存在跨分支入口')
        owned.update(members)
        branches[root] = members
    if any(source not in owned for source in graph.get_prev_nodes(join)):
        reject('汇合节点只能接收本 fork 的分支')
    outputs = declaration['outputs']
    if not isinstance(outputs, dict) or set(outputs) - branches.keys():
        reject('合并输出必须指向声明分支')
    destinations: set[str] = set()
    for mapping in outputs.values():
        if not isinstance(mapping, dict):
            reject('分支输出必须为名称映射')
        for source, destination in mapping.items():
            if not isinstance(source, str) or not source.strip() or not isinstance(destination, str) or not destination.strip() or destination in destinations:
                reject('合并输出名称无效或重复')
            destinations.add(destination)
    return StructuredFork(join, branches, outputs)


def direct_members(graph: ExecutionGraph) -> set[str]:
    """Nodes owned by this scheduler, excluding delegated fork bodies."""
    delegated: set[str] = set()
    for identity, node in graph.nodes.items():
        if 'parallel' in node.data.get('config', node.data):
            for members in structured_fork(graph, identity).branches.values():
                delegated.update(members)
    return graph.nodes.keys() - delegated
