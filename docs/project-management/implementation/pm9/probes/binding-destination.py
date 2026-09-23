"""Measure AU-08 binding conflict destination; exit zero is not acceptance."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from tests.contract.test_project_automations import body, client

with TemporaryDirectory(prefix="pm9-binding-audit-") as directory:
    api, project_id, workflow_id = client(Path(directory))
    prefix = f"/api/v1/projects/{project_id}/automations"
    try:
        created = api.post(
            prefix, json=body(workflow_id), headers={"Idempotency-Key": str(uuid4())}
        )
        assert created.status_code == 201, created.text
        original = created.json()
        duplicate = api.post(
            prefix,
            json={**body(workflow_id), "name": "second"},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert duplicate.status_code == 409, duplicate.text
        error = duplicate.json()["error"]
        assert error["code"] == "WORKFLOW_ALREADY_BOUND"
        details = error["details"]
        print(
            json.dumps(
                {
                    "scope": "HTTP router/service/real SQLite contract fixture; not production bootstrap or packaged browser",
                    "originalProjectId": project_id,
                    "originalAutomationId": original["automationId"],
                    "duplicateResponse": duplicate.json(),
                    "destinationProvided": project_id in json.dumps(details)
                    and original["automationId"] in json.dumps(details),
                    "retainedAutomationCount": api.get(prefix).json()["total"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        api.close()
        api.app.state.automation_factory.kw["bind"].dispose()
