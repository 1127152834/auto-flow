from __future__ import annotations

import copy

import pytest

from autoflow.domain.workflows.document import WorkflowDraft
from autoflow.domain.workflows.errors import WorkflowDocumentError


def _payload() -> dict:
    return {
        "id": "workflow",
        "name": "真实保存",
        "schemaVersion": 3,
        "futureTopLevel": {"keep": [1, True, None]},
        "nodes": [
            {
                "id": "open",
                "type": "open_page",
                "position": {"x": 10, "y": 20},
                "style": {"width": 260},
                "selected": True,
                "dragging": True,
                "data": {
                    "moduleType": "open_page",
                    "url": "https://example.invalid",
                    "futureNodeField": "保留",
                },
            },
            {
                "id": "click",
                "type": "click_element",
                "position": {"x": 320, "y": 20},
                "data": {"moduleType": "click_element", "selector": "#submit"},
            },
        ],
        "edges": [
            {
                "id": "edge",
                "source": "open",
                "target": "click",
                "selected": True,
                "futureEdgeField": "保留",
            }
        ],
        "variables": [{"name": "count", "type": "number", "value": 1}],
        "viewport": {"x": 2, "y": 3, "zoom": 0.9},
    }


def test_document_roundtrip_separates_layout_and_preserves_unknown_fields() -> None:
    payload = _payload()
    original = copy.deepcopy(payload)

    draft = WorkflowDraft.from_payload(payload)

    assert payload == original
    assert draft.document["futureTopLevel"] == {"keep": [1, True, None]}
    assert draft.document["nodes"][0]["data"]["futureNodeField"] == "保留"
    assert "position" not in draft.document["nodes"][0]
    assert "selected" not in draft.document["nodes"][0]
    assert "dragging" not in draft.document["nodes"][0]
    assert draft.layout == {
        "nodes": {
            "open": {"position": {"x": 10, "y": 20}, "style": {"width": 260}},
            "click": {"position": {"x": 320, "y": 20}},
        },
        "viewport": {"x": 2, "y": 3, "zoom": 0.9},
    }
    restored = draft.to_payload()
    assert restored["futureTopLevel"] == payload["futureTopLevel"]
    assert restored["nodes"][0]["position"] == {"x": 10, "y": 20}
    assert restored["nodes"][0]["style"] == {"width": 260}
    assert restored["edges"][0]["futureEdgeField"] == "保留"
    assert "selected" not in restored["nodes"][0]
    assert "dragging" not in restored["nodes"][0]
    assert "selected" not in restored["edges"][0]


@pytest.mark.parametrize(
    ("patch", "path", "code"),
    [
        (
            {"nodes": [{"id": "open"}, {"id": "open"}]},
            "nodes.1.id",
            "DUPLICATE_NODE_ID",
        ),
        (
            {"edges": [{"id": "edge", "source": "open", "target": "missing"}]},
            "edges.0.target",
            "DANGLING_EDGE",
        ),
        ({"variables": {"name": "bad"}}, "variables", "INVALID_DOCUMENT"),
    ],
)
def test_structural_damage_is_rejected_but_incomplete_config_is_allowed(
    patch: dict, path: str, code: str
) -> None:
    payload = _payload()
    payload.update(patch)

    with pytest.raises(WorkflowDocumentError) as raised:
        WorkflowDraft.from_payload(payload)

    assert raised.value.code == code
    assert raised.value.details["path"] == path

    incomplete = _payload()
    incomplete["nodes"][0]["data"]["url"] = ""
    assert (
        WorkflowDraft.from_payload(incomplete).to_payload()["nodes"][0]["data"]["url"]
        == ""
    )


def test_non_json_values_are_rejected_without_coercion() -> None:
    payload = _payload()
    payload["futureTopLevel"] = float("nan")

    with pytest.raises(WorkflowDocumentError) as raised:
        WorkflowDraft.from_payload(payload)

    assert raised.value.code == "INVALID_DOCUMENT"
    assert raised.value.details["path"] == "document"
