"""Validation and orchestration for the Laya experiment."""

import json
import re
from typing import Any, Protocol


class LayaError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class LayaRuntimePort(Protocol):
    def status(self) -> dict[str, Any]: ...

    async def predict(
        self, model: str, state: str | dict[str, Any] | list[Any], questions: dict[str, dict[str, Any]]
    ) -> dict[str, Any]: ...


_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}$")


def validate_experiment(
    state: str | dict[str, Any] | list[Any], questions: dict[str, dict[str, Any]]
) -> None:
    if isinstance(state, str):
        content = state
    else:
        try:
            content = json.dumps(state, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        except (TypeError, ValueError, RecursionError) as exc:
            raise LayaError(422, "LAYA_INVALID_INPUT", "JSON 输入无效") from exc
    if not content.strip() or len(content.encode("utf-8")) > 16 * 1024:
        raise LayaError(422, "LAYA_INVALID_INPUT", "输入不能为空，且不得超过 16 KiB")
    if not 1 <= len(questions) <= 8:
        raise LayaError(422, "LAYA_INVALID_QUESTIONS", "每次需配置 1 到 8 个问题")
    for question_id, question in questions.items():
        if not _ID.fullmatch(question_id):
            raise LayaError(422, "LAYA_INVALID_QUESTIONS", "问题 ID 须以字母开头，只能包含字母、数字和下划线，最长 40 位")
        if not question["instructions"].strip():
            raise LayaError(422, "LAYA_INVALID_QUESTIONS", "问题说明不能为空")
        criteria = question.get("criteria")
        if question["type"] == "choice":
            if not isinstance(criteria, dict) or not 2 <= len(criteria) <= 10:
                raise LayaError(422, "LAYA_INVALID_QUESTIONS", "choice 需要 2 到 10 个候选项")
            for key, description in criteria.items():
                if not _ID.fullmatch(key) or not description.strip() or len(description) > 160:
                    raise LayaError(422, "LAYA_INVALID_QUESTIONS", "候选键或描述无效")
        elif question["type"] == "score":
            if not isinstance(criteria, list) or not 2 <= len(criteria) <= 10:
                raise LayaError(422, "LAYA_INVALID_QUESTIONS", "score 需要 2 到 10 个有序等级")
            if any(not label.strip() or len(label) > 160 for label in criteria) or len({label.strip() for label in criteria}) != len(criteria):
                raise LayaError(422, "LAYA_INVALID_QUESTIONS", "评分等级不能为空或重复，且每项最多 160 字")


class LayaService:
    def __init__(self, runtime: LayaRuntimePort) -> None:
        self.runtime = runtime

    def status(self) -> dict[str, Any]:
        return self.runtime.status()

    async def predict(
        self, model: str, state: str | dict[str, Any] | list[Any], questions: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        validate_experiment(state, questions)
        return await self.runtime.predict(model, state, questions)
