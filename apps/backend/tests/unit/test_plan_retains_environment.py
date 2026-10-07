"""M5 5B-A1: the preview pre-check looks at every End in the frozen plan, not only the main document."""

from autoflow.application.project_runs.end import plan_retains_environment


def _end(retain, node_id="end"):
    return {"id": node_id, "type": "project_end", "data": {"moduleType": "project_end", "retainEnvironment": retain, "saveMode": "save_as"}}


def _step(node_id="step"):
    return {"id": node_id, "type": "set_variable", "data": {"moduleType": "set_variable", "variableName": "a", "variableValue": "b"}}


def test_main_document_end_decides():
    assert plan_retains_environment({"document": {"nodes": [_step(), _end(True)]}}) is True
    assert plan_retains_environment({"document": {"nodes": [_step(), _end(False)]}}) is False
    assert plan_retains_environment({"document": {"nodes": [_step()]}}) is False


def test_an_end_inside_a_sub_workflow_counts():
    plan = {"document": {"nodes": [_step(), _end(False)]}, "workflowDependencies": {"child": {"nodes": [_end(True, "child-end")]}}}
    assert plan_retains_environment(plan) is True


def test_an_end_inside_a_custom_module_counts():
    plan = {"document": {"nodes": [_step()]}, "customModuleDependencies": {"m": {"workflow": {"nodes": [_end(True, "module-end")]}}}}
    assert plan_retains_environment(plan) is True


def test_an_invalid_end_is_not_refused_here_it_fails_in_its_own_validation():
    plan = {"document": {"nodes": [{"id": "end", "type": "project_end", "data": {"moduleType": "project_end", "saveMode": "not-a-mode"}}]}}
    assert plan_retains_environment(plan) is False
