"""Page aliases follow the same definite-assignment rules as control paths."""
from typing import Any

from .control_values import fail


def validate_page_aliases(document: dict[str, Any], plan: list[dict[str, Any]], *, allow_missing: bool = False) -> None:
    nodes = {n['id']: n for n in document['nodes']}

    def walk(steps: list[dict[str, Any]], available: set[str]) -> tuple[set[str], bool]:
        for step in steps:
            node = nodes[step['nodeId']]
            kind, c = node['type'], node['config']
            alias = c.get('pageAlias')
            if kind in {'switch_page', 'close_page'} and alias not in available and not allow_missing:
                fail('PAGE_ALIAS_UNAVAILABLE', '页面别名在此路径尚未产生', ['config', 'pageAlias'], node['id'])
            if kind == 'close_page':
                available.discard(alias)
            if kind == 'open_page' and alias:
                available.add(alias)
            if c.get('newPageAlias'):
                available.add(c['newPageAlias'])
            if kind in {'break_loop', 'continue_loop'}:
                return available, False
            if kind == 'condition':
                yes, yr = walk(step['true'], set(available))
                no, nr = walk(step['false'], set(available))
                reaching = [v for v, reaches in ((yes, yr), (no, nr)) if reaches]
                if not reaching:
                    return available, False
                available = set.intersection(*reaching)
            if kind == 'loop':
                after, _ = walk(step['body'], set(available))
                available &= after
        return available, True
    walk(plan, set())
