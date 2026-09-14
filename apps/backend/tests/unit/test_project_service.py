from datetime import UTC, datetime

import pytest

from autoflow.application.projects.service import ProjectService
from autoflow.domain.projects.models import ProjectError


class MemoryProjects:
    def __init__(self):
        self.item = None

    def create(self, record, operation):
        self.item = record
        return record, operation.with_result(record.project_id, record)

    def update(self, project_id, patch, expected_revision, operation):
        assert self.item
        self.item = self.item.patched(patch, datetime.now(UTC))
        return self.item, operation.with_result(project_id, self.item)

    def get(self, project_id):
        return self.item if self.item and self.item.project_id == project_id else None

    def list(self, **_query):
        return [self.item] if self.item else [], 1 if self.item else 0

    def open(self, project_id, now):
        self.item = self.item.opened(now)
        return self.item

    def get_operation(self, **_query):
        return None

    def list_operations(self, **_query):
        return [], 0


def test_create_normalizes_text_and_supplies_default_resources():
    service = ProjectService(MemoryProjects())
    project, _operation, replayed = service.create(
        " key ", {"name": "  项目 🚀  ", "description": " 说明 "}
    )
    assert replayed is False
    assert project.name == "项目 🚀"
    assert project.description == "说明"
    assert project.default_resources == {
        "profileId": None,
        "proxy": {"mode": "sourceDefault"},
        "modelProviderId": None,
    }
    assert project.management_revision == 1


@pytest.mark.parametrize("name", ["   ", "x" * 37])
def test_name_uses_unicode_codepoint_limit(name):
    with pytest.raises(ProjectError) as caught:
        ProjectService(MemoryProjects()).create(
            "key", {"name": name, "description": ""}
        )
    assert caught.value.code == "VALIDATION_ERROR"


def test_resources_require_a_complete_valid_combination():
    with pytest.raises(ProjectError) as caught:
        ProjectService(MemoryProjects()).create(
            "key",
            {
                "name": "A",
                "description": "",
                "defaultResources": {"proxy": {"mode": "fixed"}},
            },
        )
    assert caught.value.code == "VALIDATION_ERROR"


def test_update_requires_a_field_beyond_expected_revision():
    with pytest.raises(ProjectError) as caught:
        ProjectService(MemoryProjects()).update(
            "p", "key", {"expectedManagementRevision": 1}
        )
    assert caught.value.code == "VALIDATION_ERROR"
