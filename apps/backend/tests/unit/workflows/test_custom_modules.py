from __future__ import annotations

import pytest

from autoflow.domain.workflows.errors import WorkflowDocumentError
from autoflow.domain.workflows.modules import (
    CustomModuleDraft,
    custom_module_dependencies,
)


def test_custom_module_dependencies_preserve_first_seen_order_and_deduplicate() -> None:
    workflow = {
        "nodes": [
            {
                "id": "plain",
                "type": "set_variable",
                "data": {"moduleType": "set_variable", "customModuleId": "ignored"},
            },
            {
                "id": "first",
                "type": "custom_module",
                "data": {"moduleType": "custom_module", "customModuleId": "module-a"},
            },
            {
                "id": "second",
                "type": "custom_module",
                "data": {
                    "moduleType": "custom_module",
                    "config": {"customModuleId": "module-b"},
                },
            },
            {
                "id": "duplicate",
                "type": "custom_module",
                "data": {"moduleType": "custom_module", "customModuleId": "module-a"},
            },
        ]
    }

    assert custom_module_dependencies(workflow) == ("module-a", "module-b")


def test_custom_module_workflow_requires_the_frozen_node_shape() -> None:
    with pytest.raises(WorkflowDocumentError) as invalid:
        CustomModuleDraft.from_payload(
            {
                "name": "missing_position",
                "display_name": "缺少位置",
                "workflow": {
                    "nodes": [
                        {
                            "id": "value",
                            "type": "moduleNode",
                            "data": {"moduleType": "set_variable"},
                        }
                    ]
                },
            }
        )

    assert invalid.value.code == "CUSTOM_MODULE_INVALID"
    assert invalid.value.details == {"path": "workflow.nodes.0.position"}
