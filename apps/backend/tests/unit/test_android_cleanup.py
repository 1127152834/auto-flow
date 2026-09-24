from autoflow.application.android.cleanup import preview_cleanup


def test_cleanup_preview_only_reports_owned_labeled_resources():
    result = preview_cleanup([{"id": "v1", "workspaceId": "w", "size": 12}, {"id": "foreign", "workspaceId": "other", "size": 90}], "w")
    assert [item["id"] for item in result] == ["v1"]
