"""Remediation M4 S6 (R4-05; AC4-04): a browser starts only behind an exit that matches the identity."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from autoflow.application.workflows.browser_resources import WorkflowBrowserResources
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.profiles.models import Profile, ProfileBrowserProxy, ProfileSpec
from autoflow.domain.workflows.runtime import WorkflowRuntimeError

VERSION = "146.0.7680.177.5"


def _resources(tmp_path: Path, exits: list[tuple[str | None, str | None]], proxy: ProfileBrowserProxy | None):
    now = datetime.now(UTC)
    profile = Profile(str(uuid4()), ProfileSpec.from_values({"name": "身份模板", "browser_version": VERSION, "geoip": False}), 31415, now, now)
    executable = tmp_path / "chrome.exe"
    executable.write_bytes(b"")
    located: list[str | None] = []

    def locate(url: str | None):
        located.append(url)
        return exits[min(len(located), len(exits)) - 1]

    async def resolve_proxy(*_args, **_kwargs):
        return proxy

    resources = WorkflowBrowserResources(
        SimpleNamespace(get=lambda _: profile), lambda: [InstalledKernel("public", VERSION, executable, 0)], resolve_proxy,
        lambda: None, SimpleNamespace(guard=lambda _: nullcontext()), lambda _: nullcontext(), locate_exit=locate,
    )
    return resources, profile, located


def _request(resources, profile, region):
    return {**resources.freeze(profile.id), "identity": {"identityId": "i1", "seed": 123456789, "region": region}}


@pytest.mark.asyncio
async def test_a_mismatched_exit_refuses_to_start_and_names_both_regions(tmp_path):
    proxy = ProfileBrowserProxy("socks5://203.0.113.9:1080", "user", "p@ss", "member-1")
    resources, profile, located = _resources(tmp_path, [("America/New_York", "203.0.113.9")], proxy)
    with pytest.raises(WorkflowRuntimeError) as raised:
        await resources.acquire(_request(resources, profile, {"timezone": "Asia/Shanghai"}), str(uuid4()))
    assert raised.value.code == "IDENTITY_REGION_MISMATCH"
    assert raised.value.message == "出口 IP 203.0.113.9 位于 America/New_York，与身份地区 Asia/Shanghai 不一致"
    assert located == ["socks5://user:p%40ss@203.0.113.9:1080"]  # credentials go into the lookup URL, encoded


@pytest.mark.asyncio
async def test_a_matching_exit_starts_with_the_identity_seed_and_is_cached(tmp_path):
    resources, profile, located = _resources(tmp_path, [("Asia/Shanghai", "1.2.3.4")], None)
    request = _request(resources, profile, {"timezone": "Asia/Shanghai", "locale": "zh-CN"})
    first = await resources.acquire(request, str(uuid4()))
    first.release()
    second = await resources.acquire(request, str(uuid4()))
    second.release()
    assert first.browser["fingerprintSeed"] == 123456789 and first.browser["timezone"] == "Asia/Shanghai"
    assert located == [None]  # the second launch reused the ten-minute exit lookup


@pytest.mark.asyncio
async def test_an_unlocatable_exit_warns_by_default_and_rejects_when_asked(tmp_path):
    resources, profile, located = _resources(tmp_path, [(None, None)], None)
    lease = await resources.acquire(_request(resources, profile, {"timezone": "Asia/Shanghai"}), str(uuid4()))
    lease.release()
    with pytest.raises(WorkflowRuntimeError) as raised:
        await resources.acquire(_request(resources, profile, {"timezone": "Asia/Shanghai", "unverifiedPolicy": "reject"}), str(uuid4()))
    assert raised.value.code == "IDENTITY_REGION_UNVERIFIED"
    assert len(located) == 2  # an unlocated exit is not cached


@pytest.mark.asyncio
async def test_identities_without_a_region_skip_the_lookup(tmp_path):
    resources, profile, located = _resources(tmp_path, [("Asia/Shanghai", "1.2.3.4")], None)
    lease = await resources.acquire(_request(resources, profile, {}), str(uuid4()))
    lease.release()
    assert located == []
