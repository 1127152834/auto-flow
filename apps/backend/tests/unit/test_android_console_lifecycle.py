import pytest

from autoflow.application.android.console import AndroidConsole
from autoflow.domain.android.ports import AndroidError


@pytest.mark.asyncio
async def test_heartbeat_requires_session_identity_and_generation():
    console = AndroidConsole(None, None, None, None)
    console.sessions["s"] = {
        "view": {"id": "s", "generation": 3, "state": "connected", "clientSessionId": "client"},
        "clientSessionId": "client",
        "seen": 0,
    }
    view = await console.heartbeat("s", "client", 3)
    assert view["id"] == "s"
    with pytest.raises(AndroidError):
        await console.heartbeat("s", "other", 3)
    with pytest.raises(AndroidError):
        await console.heartbeat("s", "client", 2)
