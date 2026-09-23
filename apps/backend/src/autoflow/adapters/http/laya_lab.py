"""Local-only HTTP contract for the Laya decision experiment."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from autoflow.application.lab.service import LayaError, LayaService

from .errors import BrowserErrorEnvelope, error_response


class ChoiceQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["choice"]
    instructions: str = Field(min_length=1, max_length=256)
    criteria: dict[str, str] = Field(min_length=2, max_length=10)


class ScoreQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["score"]
    instructions: str = Field(min_length=1, max_length=256)
    criteria: list[str] = Field(min_length=2, max_length=10)


class NoulQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["noul"]
    instructions: str = Field(min_length=1, max_length=256)


Question = Annotated[ChoiceQuestion | ScoreQuestion | NoulQuestion, Field(discriminator="type")]


class LayaPredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: Literal["auto", "english", "multilingual", "typed-decisions"]
    state: str | dict[str, Any] | list[Any]
    questions: dict[str, Question] = Field(min_length=1, max_length=8)


class ChoiceAnswer(BaseModel):
    type: Literal["choice"]
    choice: str
    probabilities: dict[str, float]
    confidence: float


class ScoreAnswer(BaseModel):
    type: Literal["score"]
    score: float
    legend: dict[str, str]
    probabilities: dict[str, float]
    confidence: float


class NoulAnswer(BaseModel):
    type: Literal["noul"]
    noul: float
    probabilities: dict[str, float]
    confidence: float


Answer = Annotated[ChoiceAnswer | ScoreAnswer | NoulAnswer, Field(discriminator="type")]


class LayaRoutingRead(BaseModel):
    requested: str
    selected: str
    reason: str
    repo: str


class LayaUsageRead(BaseModel):
    inputTokens: int


class LayaTimingRead(BaseModel):
    loadMs: float
    inferenceMs: float
    totalMs: float


class LayaRuntimeRead(BaseModel):
    checkpoint: str
    revision: str
    device: Literal["cpu", "cuda", "mps"]


class LayaPredictRead(BaseModel):
    answers: dict[str, Answer]
    routing: LayaRoutingRead
    usage: LayaUsageRead
    timing: LayaTimingRead
    runtime: LayaRuntimeRead


class LayaModelStatusRead(BaseModel):
    key: str
    state: Literal["not_downloaded", "cached", "downloading", "loading", "ready", "failed", "available"]
    device: str | None = None


class LayaStatusRead(BaseModel):
    busy: bool
    models: list[LayaModelStatusRead]


def laya_lab_router(service: LayaService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/lab/laya", tags=["lab-laya"])

    @router.get("/status", response_model=LayaStatusRead)
    def status() -> dict[str, Any]:
        return service.status()

    @router.post(
        "/predict",
        response_model=LayaPredictRead,
        responses={code: {"model": BrowserErrorEnvelope} for code in (409, 422, 503, 504)},
    )
    async def predict(body: LayaPredictRequest) -> LayaPredictRead | Any:
        try:
            questions = {key: value.model_dump() for key, value in body.questions.items()}
            result = await service.predict(body.model, body.state, questions)
            return LayaPredictRead.model_validate(result)
        except LayaError as exc:
            return error_response(exc.status, exc.code, str(exc))

    return router
