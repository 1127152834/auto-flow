from copy import deepcopy
from typing import Any

WORKFLOW_ID = "d45f286f-129d-4e3b-a09b-995c3b491609"
SOURCE_REVISION = "5ccb900e8dcf1530aae66f676d87593c416c7ebb"


def workflow_payload(workflow_id: str = WORKFLOW_ID) -> dict:
    nodes: list[dict[str, Any]] = [
        {
            "id": "open",
            "type": "open_page",
            "position": {"x": 100, "y": 80},
            "width": 220,
            "height": 72,
            "dimensions": {"width": 220, "height": 72},
            "style": {"width": 220, "height": 72},
            "data": {
                "label": "打开网页",
                "moduleType": "open_page",
                "url": "https://example.test/",
                "timeout": 60,
            },
        },
        {
            "id": "input",
            "type": "input_text",
            "position": {"x": 100, "y": 200},
            "data": {
                "label": "输入文本",
                "moduleType": "input_text",
                "selector": "#name",
                "text": "{用户名}",
                "clearBefore": True,
            },
        },
        {
            "id": "click",
            "type": "click_element",
            "position": {"x": 100, "y": 320},
            "data": {
                "label": "点击元素",
                "moduleType": "click_element",
                "selector": "#submit",
            },
        },
        {
            "id": "read",
            "type": "get_element_info",
            "position": {"x": 100, "y": 440},
            "data": {
                "label": "读取文本",
                "moduleType": "get_element_info",
                "selector": "#result",
                "attribute": "text",
                "variableName": "结果",
            },
        },
    ]
    return {
        "id": workflow_id,
        "source": {"product": "WebRPA", "commit": SOURCE_REVISION},
        "format": {"kind": "webrpa-workflow", "version": 1},
        "content": {
            "id": "studio-local-workflow",
            "name": "测试流程",
            "nodes": nodes,
            "edges": [
                {
                    "id": f"edge-{index}",
                    "source": nodes[index]["id"],
                    "target": nodes[index + 1]["id"],
                    "sourceHandle": None,
                    "targetHandle": None,
                    "type": "smoothstep",
                }
                for index in range(len(nodes) - 1)
            ],
            "variables": [
                {
                    "name": "用户名",
                    "value": "测试用户",
                    "type": "string",
                    "scope": "global",
                    "builtin": False,
                }
            ],
            "createdAt": "2026-09-14T00:00:00.000Z",
            "updatedAt": "2026-09-14T00:00:01.000Z",
        },
    }


def transient_payload() -> dict:
    payload = deepcopy(workflow_payload())
    node = payload["content"]["nodes"][0]
    node.update(
        selected=True,
        dragging=True,
        resizing=True,
        measured={"width": 219.75, "height": 71.5},
    )
    node["data"]["isHighlighted"] = True
    node["data"]["__aiSpawning"] = True
    payload["content"]["edges"][0]["selected"] = True
    return payload


def grouped_payload() -> dict:
    payload = workflow_payload()
    payload["content"]["nodes"] = [
        {
            "id": "group",
            "type": "group",
            "position": {"x": 40, "y": 40},
            "style": {"width": 480, "height": 300},
            "width": 480,
            "height": 300,
            "dimensions": {"width": 480, "height": 300},
            "data": {
                "label": "",
                "moduleType": "group",
                "color": "#3b82f6",
                "width": 480,
                "height": 300,
            },
        },
        {
            "id": "child",
            "type": "open_page",
            "position": {"x": 24, "y": 52},
            "parentId": "group",
            "extent": "parent",
            "dimensions": {"width": 220, "height": 72},
            "width": 220,
            "height": 72,
            "data": {
                "label": "打开网页",
                "moduleType": "open_page",
                "url": "https://example.test/",
            },
        },
    ]
    payload["content"]["edges"] = []
    return payload
