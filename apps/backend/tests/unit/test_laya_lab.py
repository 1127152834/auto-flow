import asyncio
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.laya_lab import laya_lab_router
from autoflow.application.lab.service import LayaError, LayaService, validate_experiment
from autoflow.providers.laya.runtime import LayaRuntime

QUESTIONS = {"department": {"type": "choice", "instructions": "Which team?", "criteria": {"billing": "payments", "technical": "bugs"}}}


def test_input_validation_and_http_contract() -> None:
    class FakeRuntime:
        def status(self) -> dict[str, Any]:
            return {"busy": False, "models": [{"key": "english", "state": "not_downloaded", "device": None}]}

        async def predict(self, model: str, state: Any, questions: Any) -> dict[str, Any]:
            if state == "slow":
                raise LayaError(504, "LAYA_TIMEOUT", "模型推理超时")
            return {
                "answers": {"department": {"type": "choice", "choice": "billing", "probabilities": {"billing": 0.9, "technical": 0.1}, "confidence": 0.8}},
                "routing": {"requested": model, "selected": "english", "reason": "explicit", "repo": "convaiinnovations/laya"},
                "usage": {"inputTokens": 12}, "timing": {"loadMs": 0, "inferenceMs": 2, "totalMs": 2},
                "runtime": {"checkpoint": "english", "revision": "test", "device": "cpu"},
            }

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(laya_lab_router(LayaService(FakeRuntime())))
    with TestClient(app) as client:
        assert client.get("/api/v1/lab/laya/status").json()["models"][0]["state"] == "not_downloaded"
        response = client.post("/api/v1/lab/laya/predict", json={"model": "english", "state": "Double charge", "questions": QUESTIONS})
        assert response.status_code == 200
        assert response.json()["answers"]["department"]["probabilities"]["billing"] == 0.9
        invalid = client.post("/api/v1/lab/laya/predict", json={"model": "english", "state": " ", "questions": QUESTIONS})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "LAYA_INVALID_INPUT"
        timeout = client.post("/api/v1/lab/laya/predict", json={"model": "english", "state": "slow", "questions": QUESTIONS})
        assert timeout.status_code == 504
        assert timeout.json()["error"]["code"] == "LAYA_TIMEOUT"
    with pytest.raises(LayaError, match="候选"):
        validate_experiment("ok", {"x": {"type": "choice", "instructions": "?", "criteria": {"only": "one"}}})
    with pytest.raises(LayaError, match="候选"):
        validate_experiment("ok", {"x": {"type": "choice", "instructions": "?", "criteria": {"yes": " ", "no": "No"}}})


def test_upstream_router_selects_multilingual_without_loading_weights() -> None:
    from laya import Router

    router = Router()
    assert router.route("我的账户被重复扣款，请退款", QUESTIONS).model == "multilingual"
    assert router.loaded == []


def test_token_preflight_rejects_truncation(tmp_path: Path) -> None:
    class Tokenizer:
        mask_token = "[MASK]"

        def __call__(self, value: str, **_kwargs: Any) -> dict[str, list[int]]:
            return {"input_ids": list(range(len(value)))}

    agent = SimpleNamespace(tok=Tokenizer(), cfg={"max_len": 80, "head_max_len": 60},
                            _to_internal=lambda q: {"t": q["type"], "ins": q["instructions"], "crit": q["criteria"]})
    runtime = LayaRuntime(tmp_path)
    with pytest.raises(LayaError) as error:
        runtime._check_token_budget(agent, "x" * 100, QUESTIONS)
    assert error.value.code == "LAYA_TOKEN_LIMIT"
    runtime.close()


def test_download_failure_returns_retryable_http_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class FakeRouter:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def route(self, *_args: Any, **_kwargs: Any) -> dict[str, str]:
            return {"model": "english", "reason": "explicit"}

    fake_laya = ModuleType("laya")
    fake_laya.Router = FakeRouter  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "laya", fake_laya)

    def unavailable(**_kwargs: Any) -> None:
        raise OSError("download unavailable")

    monkeypatch.setattr("huggingface_hub.snapshot_download", unavailable)
    runtime = LayaRuntime(tmp_path)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(laya_lab_router(LayaService(runtime)))
    with TestClient(app) as client:
        response = client.post("/api/v1/lab/laya/predict", json={"model": "english", "state": "Double charge", "questions": QUESTIONS})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "LAYA_MODEL_UNAVAILABLE"
        status = client.get("/api/v1/lab/laya/status").json()
        assert status["busy"] is False
        assert status["models"][0]["state"] == "failed"
    runtime.close()


@pytest.mark.asyncio
async def test_lazy_runtime_reuses_model_and_routes_chinese(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    builds: list[str] = []

    class FakeAgent:
        device = SimpleNamespace(type="cpu")

        def predict(self, state: Any, questions: Any) -> dict[str, Any]:
            return {"answers": {"risk": {"type": "noul", "noul": 0.7, "confidence": 0.7}}, "usage": {"input_tokens": 8}}

    class FakeRouter:
        def __init__(self, **kwargs: Any) -> None:
            assert kwargs["max_loaded"] == 2
            self.agents: dict[str, FakeAgent] = {}

        @property
        def loaded(self) -> list[str]:
            return list(self.agents)

        def route(self, state: Any, _questions: Any, model: str | None = None) -> dict[str, str]:
            key = model or ("multilingual" if "退款" in str(state) else "english")
            return {"model": key, "reason": "test routing"}

        def load(self, key: str) -> FakeAgent:
            if key not in self.agents:
                builds.append(key)
                self.agents[key] = FakeAgent()
            return self.agents[key]

    fake_laya = ModuleType("laya")
    fake_laya.Router = FakeRouter  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "laya", fake_laya)
    runtime = LayaRuntime(tmp_path)
    monkeypatch.setattr(runtime, "_cached", lambda _key: True)
    monkeypatch.setattr(runtime, "_check_token_budget", lambda *_args: None)
    assert runtime.status()["models"][0]["state"] == "cached"
    assert runtime.status()["models"][-1] == {"key": "auto", "state": "available", "device": None}
    q = {"risk": {"type": "noul", "instructions": "Refund?"}}
    first = await runtime.predict("auto", "请退款", q)
    second = await runtime.predict("auto", "请退款", q)
    assert first["routing"]["selected"] == "multilingual"
    assert first["answers"]["risk"]["probabilities"] == {"false": 0.3, "true": 0.7}
    assert second["runtime"]["device"] == "cpu"
    assert builds == ["multilingual"]
    runtime.close()


@pytest.mark.asyncio
async def test_timeout_keeps_runtime_busy_until_worker_finishes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runtime = LayaRuntime(tmp_path)

    def slow(*_args: Any) -> Any:
        time.sleep(0.08)
        return None

    monkeypatch.setattr(runtime, "_prepare", slow)
    original = asyncio.wait_for
    monkeypatch.setattr(asyncio, "wait_for", lambda future, _timeout: original(future, 0.01))
    with pytest.raises(LayaError) as error:
        await runtime.predict("english", "x", QUESTIONS)
    assert error.value.status == 504
    assert runtime.status()["busy"] is True
    await asyncio.sleep(0.1)
    assert runtime.status()["busy"] is False
    runtime.close()
