"""Remediation M2 R2-18/19/21: signature parsing, references, context and masking."""

import pytest

from autoflow.domain.workflows.project_inputs import input_context
from autoflow.domain.workflows.signature import (
    parse_signature,
    reference_issues,
    sensitive_references,
)
from autoflow.providers.browser.project_graph import ProjectGraphExecutor

SIGNATURE = {"inputs": [{"key": "account", "name": "账号", "fields": [
    {"key": "user", "name": "用户名", "type": "string", "required": True},
    {"key": "password", "name": "密码", "type": "string", "required": True, "sensitive": True},
]}]}


def snapshot():
    return [{
        "inputId": "i1", "signatureInput": "account", "recordRef": {"recordKey": {"type": "text", "value": "r1"}},
        "values": [{"fieldId": "f-user", "value": "alice"}, {"fieldId": "f-pass", "value": "s3cret"}],
        "fieldMappings": [
            {"inputFieldId": "b1", "signatureField": "user", "fieldRef": {"fieldId": "f-user"}},
            {"inputFieldId": "b2", "signatureField": "password", "fieldRef": {"fieldId": "f-pass"}},
        ],
    }]


def test_signature_keys_are_checked_and_names_are_display_only():
    signature, issues = parse_signature(SIGNATURE)
    assert issues == [] and signature is not None
    assert signature.input("account").field("password").sensitive is True
    _, bad = parse_signature({"inputs": [{"key": "1x", "fields": []}, {"key": "a", "fields": [{"key": "f"}, {"key": "f"}]}]})
    assert [issue.path for issue in bad] == ["signature.inputs.0.key", "signature.inputs.1.fields.1.key"]


def test_unknown_references_are_named():
    signature, _ = parse_signature(SIGNATURE)
    document = {"content": {"nodes": [{"id": "n", "data": {"text": "{input.account.age} {input.other} {$record.user}"}}]}}
    assert reference_issues(document, signature) == [("n", "流程输入「账号」没有字段「age」"), ("n", "引用了不存在的流程输入「other」")]


def test_context_exposes_groups_and_the_primary_record():
    context = input_context(snapshot(), {}, "i1")
    assert context["input"] == {"account": {"user": "alice", "password": "s3cret"}}
    assert context["$record"] == {"user": "alice", "password": "s3cret"}
    assert input_context(snapshot(), {}, None).get("$record") is None
    signature, _ = parse_signature(SIGNATURE)
    assert sensitive_references(signature, "account") == {"input.account.password", "$record.password"}


@pytest.mark.asyncio
async def test_project_runs_resolve_signature_references_and_mask_sensitive_values():
    events = []

    async def emit(*event):
        events.append(event)

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False, project_input_context=input_context(snapshot(), {}, "i1"))
    document = {"signature": SIGNATURE, "nodes": [
        {"id": "u", "data": {"moduleType": "set_variable", "variableName": "who", "variableValue": "{input.account.user}"}},
        {"id": "p", "data": {"moduleType": "set_variable", "variableName": "secret", "variableValue": "{$record.password}"}},
    ], "edges": [{"id": "e", "source": "u", "target": "p"}]}
    assert (await executor.run({"document": document}))["status"] == "succeeded"
    assert executor.context.variables["who"] == "alice"
    assert executor.context.variables["secret"] == "s3cret"
    assert "secret" in executor.context.sensitive_variables and "who" not in executor.context.sensitive_variables
    assert "s3cret" not in repr(events)
