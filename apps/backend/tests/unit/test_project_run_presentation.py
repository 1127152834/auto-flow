from types import SimpleNamespace

from autoflow.application.project_runs.presentation import prepared_node_names


def test_node_name_uses_name_then_label_then_shared_catalog():
    prepared = SimpleNamespace(
        execution_plan={
            "nodes": [
                {
                    "nodeId": "named",
                    "data": {
                        "name": " 自定义名称 ",
                        "label": "旧标题",
                        "moduleType": "open_page",
                    },
                },
                {
                    "nodeId": "labelled",
                    "data": {
                        "name": "   ",
                        "label": " 保留标题 ",
                        "moduleType": "input_text",
                    },
                },
                {
                    "nodeId": "catalogued",
                    "data": {"moduleType": "get_element_info"},
                },
                {"nodeId": "unknown", "data": {"moduleType": "future_node"}},
            ]
        }
    )

    assert prepared_node_names(prepared) == {  # type: ignore[arg-type]
        "named": "自定义名称",
        "labelled": "保留标题",
        "catalogued": "读取文本",
        "unknown": "未命名节点",
    }
