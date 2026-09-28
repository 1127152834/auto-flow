"""Frozen project-data declarations shared by admission and worker authorization."""

from collections.abc import Iterator, Mapping
from typing import Any

PROJECT_DATA_OPERATIONS = {
    "read": "readRecord",
    "query": "queryRecords",
    "update": "updateRecord",
    "status": "setRecordStatus",
    "create": "createRecord",
    "delete": "deleteRecord",
    "addField": "addField",
    "ensureField": "ensureField",
    "modifyField": "modifyField",
    "previewField": "modifyField",
}

PROJECT_DATA_ERRORS = {
    "VALIDATION_ERROR": "项目数据参数无效，请检查记录引用、字段和值的类型",
    "CAPABILITY_MISSING": "当前运行未绑定项目数据能力",
    "CAPABILITY_SCOPE_DENIED": "项目数据操作超出此节点的授权范围",
    "CAPABILITY_FACTS_INCOMPLETE": "项目数据授权或任务占用记录不完整",
    "LEASE_REVOKED": "当前任务的执行授权已失效",
    "LEASE_BUSY": "记录正在被其他任务占用",
    "REVISION_CONFLICT": "记录或数据结构已变化，请重新读取后处理冲突",
    "STATUS_PRECONDITION_FAILED": "记录当前状态不符合转换条件",
    "OPERATION_PAYLOAD_MISMATCH": "原操作标识对应的参数不一致，不能重发",
    "DATASET_GENERATION_GONE": "数据表已被替换，请重新绑定",
    "PROJECT_DATA_FAILED": "项目数据操作失败，请核对任务授权和数据状态",
}


def project_data_nodes(plan: Mapping[str, Any], module_type: str = "project_data") -> Iterator[tuple[str, Mapping[str, Any]]]:
    documents = [plan.get("document", plan)]
    documents.extend(plan.get("workflowDependencies", {}).values())
    documents.extend(
        item.get("workflow", {})
        for item in plan.get("customModuleDependencies", {}).values()
    )
    for document in documents:
        for node in document.get("nodes", ()):
            data = node.get("data", node)
            if data.get("moduleType", node.get("moduleType")) == module_type:
                yield node.get("id", node.get("nodeId")), data.get("config", data)


def project_data_manifest(plan: Mapping[str, Any]) -> dict[str, Any]:
    grants = []
    for _node_id, config in project_data_nodes(plan):
        action = config.get("action", "inputs")
        if not isinstance(action, str):
            raise TypeError("Invalid project data action")
        if action in {"inputs", "operation"}:
            continue
        if action not in PROJECT_DATA_OPERATIONS:
            raise ValueError("Unknown project data action")
        binding = config.get("binding")
        if not isinstance(binding, Mapping) or set(binding) != {
            "tableId",
            "datasetGeneration",
            "fieldIds",
        }:
            raise ValueError(
                "Project data nodes require an explicit table and field binding"
            )
        grants.append(
            {
                **binding,
                "operations": [PROJECT_DATA_OPERATIONS[action]],
                "readPurposes": ["workflow"] if action in {"read", "query"} else [],
            }
        )
    return {"tableGrants": grants}
