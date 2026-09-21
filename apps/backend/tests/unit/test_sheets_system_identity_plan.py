"""Frozen source identity plans must be verifiable without guessing row ownership."""
from uuid import UUID

import pytest

from autoflow.application.project_sync.system_identity import (
    identity_plan,
    verify_identity,
)
from autoflow.domain.projects.models import ProjectError


def test_frozen_identity_plan_verifies_only_original_column_and_rows():
    rows = [["Name"], ["one"], [], ["two"]]
    plan = identity_plan(rows, column=1, sheet_id=1000, owner="original-operation")
    assert len(plan["values"]) == 4 and plan["values"][2] == ""
    assert str(UUID(plan["values"][1])) == plan["values"][1]
    assert plan["values"][1] != plan["values"][3]
    remote = [[*row, value] if row else ["", value] for row, value in zip(rows, plan["values"], strict=True)]
    metadata = [{"metadataKey": "autoflow.systemIdentity", "metadataValue": "original-operation", "location": {"dimensionRange": {"sheetId": 1000, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2}}}]
    assert verify_identity(plan, remote, metadata)
    remote[1][0] = "changed while initializing"
    assert not verify_identity(plan, remote, metadata)
    assert rows == [["Name"], ["one"], [], ["two"]]


@pytest.mark.parametrize('mutation', ['missing', 'duplicate-marker', 'moved', 'renamed', 'partial'])
def test_unknown_initialization_needs_complete_original_evidence(mutation):
    plan = identity_plan([["Name"], ["one"]], column=1, sheet_id=1000, owner="original-operation")
    remote = [["Name", plan["values"][0]], ["one", plan["values"][1]]]
    metadata = [{"metadataKey": "autoflow.systemIdentity", "metadataValue": "original-operation", "location": {"dimensionRange": {"sheetId": 1000, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2}}}]
    if mutation == 'missing': metadata = []
    elif mutation == 'duplicate-marker': metadata *= 2
    elif mutation == 'moved': metadata[0]['location']['dimensionRange']['startIndex'] = 2
    elif mutation == 'renamed': remote[0][1] = "externally renamed"
    else: remote[1][1] = ''
    assert not verify_identity(plan, remote, metadata)


@pytest.mark.parametrize('rows', [ [["Name"], ["same"], ["same"]], [["Name", "_autoflow_id"], ["one", "foreign"]] ])
def test_identity_initialization_refuses_ambiguous_rows_or_foreign_column(rows):
    with pytest.raises(ProjectError):
        identity_plan(rows, column=2, sheet_id=1000, owner="original-operation")
