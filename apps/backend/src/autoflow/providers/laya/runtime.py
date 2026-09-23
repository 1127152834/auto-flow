"""Lazy, process-local Laya runtime. No model or torch import occurs at app startup."""

import asyncio
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

from autoflow.application.lab.service import LayaError

REVISION = "1c5edc17a7acd8701df6fc341c0d179f1c62c982"
REPO = "convaiinnovations/laya"
SUBFOLDERS = {"english": None, "multilingual": "multilingual", "typed-decisions": "typed-decisions"}


class LayaRuntime:
    def __init__(self, cache: Path) -> None:
        self.cache = cache / "laya" / REVISION
        self._lock = threading.Lock()
        self._busy = False
        self._states: dict[str, str] = {}
        self._devices: dict[str, str] = {}
        self._router: Any = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="laya-lab")

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _directory(self, key: str) -> Path:
        subfolder = SUBFOLDERS[key]
        return self.cache / subfolder if subfolder else self.cache

    def _cached(self, key: str) -> bool:
        path = self._directory(key)
        return all((path / file).is_file() for file in (
            "model.safetensors", "rl_agent_config.json", "tokenizer/tokenizer.json", "encoder/config.json"
        ))

    def _set_state(self, key: str, state: str, device: str | None = None) -> None:
        with self._lock:
            self._states[key] = state
            if device is not None:
                self._devices[key] = device

    def status(self) -> dict[str, Any]:
        with self._lock:
            busy = self._busy
            states = self._states.copy()
            devices = self._devices.copy()
        return {
            "busy": busy,
            "models": [
                {
                    "key": key,
                    "state": states.get(key, "cached" if self._cached(key) else "not_downloaded"),
                    "device": devices.get(key),
                }
                for key in SUBFOLDERS
            ] + [{"key": "auto", "state": "available", "device": None}],
        }

    def _prepare(
        self, requested: str, state: str | dict[str, Any] | list[Any], questions: dict[str, dict[str, Any]]
    ) -> tuple[str, dict[str, Any], Any, float]:
        started = time.perf_counter()
        try:
            if self._router is None:
                from laya import Router  # type: ignore[import-untyped]

                self._router = Router(models={
                    key: (str(self.cache), subfolder) for key, subfolder in SUBFOLDERS.items()
                }, max_loaded=2)
            decision = self._router.route(state, questions, model=None if requested == "auto" else requested)
            key = decision["model"]
            if not self._cached(key):
                self._set_state(key, "downloading")
                from huggingface_hub import snapshot_download

                prefix = f"{SUBFOLDERS[key]}/" if SUBFOLDERS[key] else ""
                snapshot_download(
                    repo_id=REPO,
                    revision=REVISION,
                    local_dir=str(self.cache),
                    allow_patterns=[prefix + name for name in (
                        "rl_agent_config.json", "model.safetensors", "tokenizer/*", "encoder/*"
                    )],
                )
                if not self._cached(key):
                    raise RuntimeError("Checkpoint files incomplete")
            self._set_state(key, "loading")
            agent = self._router.load(key)
            self._set_state(key, "ready", agent.device.type)
            loaded = set(self._router.loaded)
            for other in SUBFOLDERS:
                if other not in loaded and self._states.get(other) == "ready":
                    self._set_state(other, "cached")
            self._check_token_budget(agent, state, questions)
            return key, dict(decision), agent, (time.perf_counter() - started) * 1000
        except LayaError:
            raise
        except Exception as exc:
            if "key" in locals():
                self._set_state(key, "failed")
            raise LayaError(503, "LAYA_MODEL_UNAVAILABLE", "Laya 模型下载或加载失败，请检查网络与可用空间后重试") from exc

    @staticmethod
    def _check_token_budget(
        agent: Any, state: str | dict[str, Any] | list[Any], questions: dict[str, dict[str, Any]]
    ) -> None:
        from laya.common import (  # type: ignore[import-untyped]
            render_options,
            serialize_state,
        )

        tok = agent.tok
        mask = tok.mask_token
        state_tokens = tok(serialize_state(state).replace(mask, " "), add_special_tokens=False)["input_ids"]
        max_len = int(agent.cfg.get("max_len", 512))
        head_max_len = int(agent.cfg.get("head_max_len", 192))
        for question in questions.values():
            internal = agent._to_internal(question)
            instruction = str(internal["ins"]).replace(mask, " ")
            head = tok(f"{internal['t']} question: {instruction}", add_special_tokens=False)["input_ids"]
            options = [tok(" " + option.replace(mask, " "), add_special_tokens=False)["input_ids"]
                       for option in render_options(internal)]
            option_size = sum(1 + len(option) for option in options)
            if any(len(option) > 48 for option in options) or option_size > head_max_len - 16:
                raise LayaError(422, "LAYA_TOKEN_LIMIT", "候选说明超过模型的选项 token 预算，请缩短描述")
            if len(head) > head_max_len - option_size:
                raise LayaError(422, "LAYA_TOKEN_LIMIT", "问题说明超过模型的 token 预算，请缩短问题")
            state_room = max_len - len(head) - option_size - 4
            if len(state_tokens) > state_room:
                raise LayaError(422, "LAYA_TOKEN_LIMIT", f"输入超过该模型的 token 上限，请缩短内容（当前可用 {state_room} tokens）")

    def _infer(
        self, prepared: tuple[str, dict[str, Any], Any, float],
        state: str | dict[str, Any] | list[Any], questions: dict[str, dict[str, Any]], requested: str, started: float
    ) -> dict[str, Any]:
        key, decision, agent, load_ms = prepared
        infer_started = time.perf_counter()
        try:
            value = agent.predict(state, questions)
        except Exception as exc:
            raise LayaError(503, "LAYA_INFERENCE_FAILED", "Laya 推理失败，请稍后重试") from exc
        inference_ms = (time.perf_counter() - infer_started) * 1000
        self._set_state(key, "ready", agent.device.type)
        answers = value["answers"]
        for answer in answers.values():
            if answer["type"] == "noul":
                probability = float(answer["noul"])
                answer["probabilities"] = {"false": round(1 - probability, 4), "true": probability}
        return {
            "answers": answers,
            "routing": {
                "requested": requested,
                "selected": key,
                "reason": decision["reason"],
                "repo": REPO if key == "english" else f"{REPO}/{SUBFOLDERS[key]}",
            },
            "usage": {"inputTokens": value["usage"]["input_tokens"]},
            "timing": {
                "loadMs": round(load_ms, 2),
                "inferenceMs": round(inference_ms, 2),
                "totalMs": round((time.perf_counter() - started) * 1000, 2),
            },
            "runtime": {"checkpoint": key, "revision": REVISION, "device": agent.device.type},
        }

    def _finish(self) -> None:
        with self._lock:
            self._busy = False

    async def predict(
        self, model: str, state: str | dict[str, Any] | list[Any], questions: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        with self._lock:
            if self._busy:
                raise LayaError(409, "LAYA_BUSY", "已有 Laya 实验正在运行，请等待完成")
            self._busy = True
        started = time.perf_counter()
        pending: Future[Any] | None = None
        try:
            pending = self._executor.submit(self._prepare, model, state, questions)
            prepared = await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(pending)), 600)
            pending = self._executor.submit(self._infer, prepared, state, questions, model, started)
            return await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(pending)), 45)
        except TimeoutError as exc:
            raise LayaError(504, "LAYA_TIMEOUT", "Laya 模型下载、加载或推理超时；后台任务结束后可重试") from exc
        finally:
            if pending is None or pending.done():
                self._finish()
            else:
                pending.add_done_callback(lambda _future: self._finish())
