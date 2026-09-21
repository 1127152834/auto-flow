"""Reconcile owned browser directories without re-executing a workflow."""
from __future__ import annotations

import asyncio
import shutil
import signal
import sys
from pathlib import Path
from uuid import UUID

from autoflow.infrastructure.process.project_browser_processes import (
    capture_processes,
    living_processes,
    signal_processes,
)


async def recover_worker_directories(
    temp_dir: Path, run_id: str, executable: Path, *, timeout: float = 3,
) -> None:
    if str(UUID(run_id)) != run_id:
        raise RuntimeError("Invalid workflow cleanup identity")
    root = temp_dir.resolve() / "workflow-runs"
    run = root / run_id
    if _redirected(root) or _redirected(run):
        raise RuntimeError("Workflow cleanup ownership path is invalid")
    if not run.exists():
        return
    directories = list(run.iterdir())
    for directory in directories:
        suffix = directory.name.removeprefix("generation-")
        if (not directory.name.startswith("generation-") or not suffix.isdecimal()
            or str(int(suffix)) != suffix or int(suffix) < 1
            or _redirected(directory) or not directory.is_dir()):
            raise RuntimeError("Workflow cleanup generation path is invalid")
    for directory in directories:
        if sys.platform == 'win32':
            from .windows_job import cleanup_worker_job
            await asyncio.to_thread(cleanup_worker_job, directory, run_id, int(directory.name.removeprefix('generation-')), timeout)
            await asyncio.to_thread(shutil.rmtree, directory)
            continue
        owned = await asyncio.to_thread(capture_processes, 0, None, directory, executable, strict_ownership=True)
        await asyncio.to_thread(signal_processes, owned, signal.SIGTERM)
        deadline = asyncio.get_running_loop().time() + timeout
        while await asyncio.to_thread(living_processes, owned):
            if asyncio.get_running_loop().time() >= deadline:
                break
            await asyncio.sleep(.02)
        owned = await asyncio.to_thread(capture_processes, 0, None, directory, executable, owned, strict_ownership=True)
        await asyncio.to_thread(signal_processes, owned, signal.SIGKILL)
        deadline = asyncio.get_running_loop().time() + timeout
        while await asyncio.to_thread(living_processes, owned):
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError("Workflow orphan cleanup did not finish")
            await asyncio.sleep(.02)
        # No directory or process evidence is removed before native cleanup succeeds.
        try:
            await asyncio.to_thread(shutil.rmtree, directory)
        except FileNotFoundError:
            pass


def _redirected(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    return path.is_symlink() or bool(getattr(metadata, "st_file_attributes", 0) & 0x400)
