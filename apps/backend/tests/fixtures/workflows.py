from copy import deepcopy

from autoflow.domain.workflows.catalog import node_catalog


def workflow_payload(workflow_id: str = "d45f286f-129d-4e3b-a09b-995c3b491609") -> dict:
    nodes = [
        {
            "id": f"n{index}",
            "type": item["type"],
            "label": item["title"],
            "config": deepcopy(item["defaultConfig"]),
        }
        for index, item in enumerate(node_catalog())
    ]
    nodes[0]["config"]["url"] = "https://example.com"
    for node in nodes[1:5]:
        node["config"]["selector"] = "#target"
    return {
        "document": {
            "id": workflow_id,
            "name": "测试流程",
            "schemaVersion": 1,
            "nodes": nodes,
            "edges": [
                {
                    "id": f"e{index}",
                    "source": nodes[index]["id"],
                    "target": nodes[index + 1]["id"],
                    "sourceHandle": "out",
                    "targetHandle": "in",
                }
                for index in range(len(nodes) - 1)
            ],
            "variables": [],
        },
        "layout": {
            "nodes": {
                node["id"]: {"x": index * 250, "y": 0}
                for index, node in enumerate(nodes)
            },
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
    }
