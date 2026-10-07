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


def _fields(*fields):
    return {"inputs": [{"key": "g", "name": "组", "fields": list(fields)}]}


def test_sample_values_are_checked_against_the_field_type():
    signature, issues = parse_signature(_fields(
        {"key": "a", "type": "string", "sample": "x"},
        {"key": "b", "type": "number", "sample": 3.5},
        {"key": "c", "type": "boolean", "sample": False},
        {"key": "d", "type": "date", "sample": "2026-10-07"},
        {"key": "e", "type": "any", "sample": 1},
        {"key": "f", "type": "string"},
    ))
    assert issues == [] and signature is not None
    fields = signature.input("g").fields
    assert [field.sample for field in fields] == ["x", 3.5, False, "2026-10-07", 1, None]
    _, bad = parse_signature(_fields(
        {"key": "a", "type": "number", "sample": "abc"},
        {"key": "b", "type": "number", "sample": True},
        {"key": "c", "type": "boolean", "sample": "yes"},
        {"key": "d", "type": "date", "sample": "明天"},
        {"key": "e", "type": "string", "sample": 5},
    ))
    assert [issue.path for issue in bad] == [f"signature.inputs.0.fields.{i}.sample" for i in range(5)]
    assert all("样例" in issue.message for issue in bad)


def test_sample_rules_match_the_studio_editor():
    # Python's own parsers accept more than the editor does; the contract is the strict form.
    _, bad = parse_signature(_fields(
        {"key": "a", "type": "date", "sample": "20261007"},
        {"key": "b", "type": "date", "sample": "2026-W41-3"},
        {"key": "c", "type": "number", "sample": float("nan")},
        {"key": "d", "type": "number", "sample": float("inf")},
        {"key": "e", "type": "any", "sample": float("-inf")},
    ))
    assert [issue.path for issue in bad] == [f"signature.inputs.0.fields.{i}.sample" for i in range(5)]


def test_sensitive_fields_reject_samples():
    _, issues = parse_signature(_fields({"key": "pw", "type": "string", "sensitive": True, "sample": "s3cret"}))
    assert [issue.path for issue in issues] == ["signature.inputs.0.fields.0.sample"]
    assert "敏感" in issues[0].message and "s3cret" not in issues[0].message
    signature, ok = parse_signature(_fields({"key": "pw", "type": "string", "sensitive": True}))
    assert ok == [] and signature.input("g").field("pw").sample is None
