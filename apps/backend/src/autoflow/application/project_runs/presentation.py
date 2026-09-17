from __future__ import annotations

from collections.abc import Mapping

from autoflow.domain.workflows.catalog import node_catalog
from autoflow.domain.workflows.runtime import PreparedContent


def prepared_node_names(prepared: PreparedContent | None) -> dict[str, str]:
    if prepared is None:
        return {}
    result: dict[str, str] = {}
    catalog = {item["moduleType"]: item["title"] for item in node_catalog()}
    for item in prepared.execution_plan.get("nodes", ()):
        if not isinstance(item, Mapping):
            continue
        node_id, data = item.get("nodeId"), item.get("data")
        if not isinstance(node_id, str) or not isinstance(data, Mapping):
            continue
        configured = next(
            (
                value.strip()
                for value in (data.get("name"), data.get("label"))
                if isinstance(value, str) and value.strip()
            ),
            None,
        )
        result[node_id] = configured or catalog.get(
            str(data.get("moduleType")), "未命名节点"
        )
    return result
