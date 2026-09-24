from datetime import UTC, datetime

from autoflow.domain.environments.identity import (
    profile_from_request,
    request_from_identity,
    update_browser_configuration,
)
from autoflow.domain.environments.rules import environment_error
from autoflow.domain.profiles.errors import KernelNotInstalled, ProxyUnavailable
from autoflow.domain.projects.models import ProjectError
from autoflow.domain.workflows.runtime import WorkflowRuntimeError


def patch_browser_configuration(service, project_id, environment_id, key, payload):
    if set(payload) != {"browserConfiguration", "expectedMetadataRevision", "expectedContentGeneration"}:
        raise environment_error("VALIDATION_ERROR", "浏览器配置请单独保存", 422)
    expected = payload["expectedMetadataRevision"]
    generation = payload["expectedContentGeneration"]
    if any(type(value) is not int or value < 1 for value in (expected, generation)):
        raise environment_error("VALIDATION_ERROR", "环境修订无效", 422)
    operation = service._command(key, "updateEnvironment", project_id, environment_id,
                                 {"scope": "environmentConfiguration", "projectId": project_id,
                                  "environmentId": environment_id, "request": payload}, datetime.now(UTC))
    accepted, replayed = service.environments.accept_operation(operation)
    if replayed and accepted.status == "succeeded":
        return service.environments.get(project_id, environment_id), accepted, True
    if accepted.error:
        raise environment_error(accepted.error["code"], accepted.error["message"], accepted.error.get("status", 409))
    try:
        environment, active = service.environments.get_with_instance(project_id, environment_id)
        if active is not None:
            raise environment_error("ENVIRONMENT_BUSY", "请关闭当前浏览器后修改配置", 423)
        if environment.ref.metadata_revision != expected or environment.ref.content_generation != generation:
            raise environment_error("SAVE_GENERATION_CONFLICT", "环境已更新，请重新读取后修改", 409)
        identity = update_browser_configuration(environment.identity_package, payload["browserConfiguration"])
        profile = profile_from_request(request_from_identity(identity))
        if service._validate_browser_configuration is None:
            raise environment_error("RESOURCE_UNAVAILABLE", "浏览器资源校验尚未就绪", 503)
        try:
            service._validate_browser_configuration(profile.spec)
        except (KernelNotInstalled, ProxyUnavailable) as error:
            raise environment_error("RESOURCE_UNAVAILABLE", "内核未安装或代理不可用，请重新选择", 422) from error
        if service.store.generation_identity(environment_id, generation) != environment.identity_package:
            raise environment_error("ENVIRONMENT_IDENTITY_UNVERIFIED", "保存内容与环境身份不一致", 409)
        service.store.stage_configuration(accepted.operation_id, environment_id, generation, identity)

        def publish():
            try:
                digest = service.store.publish(environment_id, generation + 1, accepted.operation_id)
            except FileExistsError:
                digest = (service.store.generation_dir(environment_id, generation + 1) / ".digest").read_text().strip()
            if service.store.generation_identity(environment_id, generation + 1) != identity:
                raise environment_error("ENVIRONMENT_IDENTITY_UNVERIFIED", "发布身份与原操作不一致", 409)
            return digest

        result = service.environments.update_configuration(
            project_id, environment_id, expected, generation, identity, accepted, publish,
        )
        service.store.discard_candidate(accepted.operation_id)
        return result
    except (ProjectError, WorkflowRuntimeError) as error:
        # After publication, only the original command may reconcile the orphaned generation.
        if not service.store.generation_dir(environment_id, generation + 1).exists():
            service.environments.complete_operation(accepted, None, {
                "code": error.code, "message": error.message, "status": error.status,
            }, datetime.now(UTC))
            service.store.discard_candidate(accepted.operation_id)
        raise
