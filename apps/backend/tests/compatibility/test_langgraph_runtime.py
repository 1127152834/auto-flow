from __future__ import annotations

import asyncio
import importlib
import socket
import sqlite3
from pathlib import Path
from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class ApprovalState(TypedDict):
    command_id: str
    approved: bool | None


def _approval_graph(checkpointer):
    def request_approval(state: ApprovalState) -> ApprovalState:
        decision = interrupt({"commandId": state["command_id"], "tool": "add_node"})
        return {**state, "approved": bool(decision["approved"])}

    builder = StateGraph(ApprovalState)
    builder.add_node("approval", request_approval)
    builder.add_edge(START, "approval")
    builder.add_edge("approval", END)
    return builder.compile(checkpointer=checkpointer)


def test_sqlite_checkpoint_resumes_interrupt_after_graph_recreation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def reject_network(*_args, **_kwargs):
        raise AssertionError("LangGraph core must not open telemetry connections")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    database = tmp_path / "assistant-checkpoints.sqlite3"
    config = {"configurable": {"thread_id": "workspace/session-1"}}
    first_connection = sqlite3.connect(database, check_same_thread=False)
    first = _approval_graph(SqliteSaver(first_connection))
    paused = first.invoke(
        {"command_id": "command-1", "approved": None}, config=config
    )
    assert paused["__interrupt__"][0].value == {
        "commandId": "command-1",
        "tool": "add_node",
    }
    first_connection.close()

    second_connection = sqlite3.connect(database, check_same_thread=False)
    second = _approval_graph(SqliteSaver(second_connection))
    resumed = second.invoke(Command(resume={"approved": True}), config=config)
    second_connection.close()

    assert resumed == {"command_id": "command-1", "approved": True}


@pytest.mark.asyncio
async def test_async_graph_can_be_cancelled_without_completing_node() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    async def wait_for_release(state: ApprovalState) -> ApprovalState:
        entered.set()
        await release.wait()
        return {**state, "approved": True}

    builder = StateGraph(ApprovalState)
    builder.add_node("wait", wait_for_release)
    builder.add_edge(START, "wait")
    builder.add_edge("wait", END)
    graph = builder.compile(checkpointer=InMemorySaver())
    task = asyncio.create_task(
        graph.ainvoke(
            {"command_id": "command-2", "approved": None},
            config={"configurable": {"thread_id": "workspace/session-2"}},
        )
    )
    await entered.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


def test_pyinstaller_discovers_required_langgraph_modules() -> None:
    collect_submodules = importlib.import_module(
        "PyInstaller.utils.hooks"
    ).collect_submodules

    modules = set(collect_submodules("langgraph"))
    modules.update(collect_submodules("langgraph.checkpoint"))
    assert {
        "langgraph.graph",
        "langgraph.types",
        "langgraph.checkpoint.memory",
        "langgraph.checkpoint.sqlite",
    }.issubset(modules)
